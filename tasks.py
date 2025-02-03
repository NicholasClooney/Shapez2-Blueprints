import json


from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path


from click import Abort, confirm, prompt, secho, style
from invoke import Exit, task


ROOT = Path(__file__).parent
ITERATION_FILE = Path('iteration.json')
VERSION_FILE = Path('version.json')


BLUEPRINT_EXTENSION = ".spz2bp"


FIRST_ITERATION_NUMBER = 1


# Extensions


# Git


class GitStatus(Enum):
    ADDED = "A"
    DELETED = "D"
    MODIFIED = "M"
    RENAME = "R"
    UNTRACKED = "??"

    @property
    def message(self) -> str:
        commit_message = {
            "A": "Add",
            "D": "Delete",
            "M": "Update",
            "R": "Move|Rename",
            "??": "Add",
        }

        return commit_message[self.value]

@dataclass
class GitFileStatus:
    path: Path
    status: GitStatus

    @property
    def message(self) -> str:
        return f"{self.status.message} {self.path.stem}"

    @property
    def isBlueprintFile(self) -> bool:
        return self.path.suffix == BLUEPRINT_EXTENSION


# Version
@dataclass
class Version:
    version: str


# Iteration Related Models


@dataclass
class BlueprintIterationModel:
    name: str
    path: str # JSON serialization does not support `pathlib.Path`
    iteration: int = FIRST_ITERATION_NUMBER


# The `iteration.json` file
@dataclass
class Iteration:
    iterations: dict[str, BlueprintIterationModel]

    @staticmethod
    def from_dict(dict: dict):
        return Iteration(
            iterations={key: BlueprintIterationModel(**value) for key, value in dict["iterations"].items()}
        )


@task
def version_and_commit(c, staged_only=False):
    """
    Currently it only handles addition and updates.
    It does NOT handle renames yet.
    """
    command = "git status --porcelain"

    output = c.run(command, hide=True).stdout

    statuses = []

    secho("git status", bold=True)
    for line in output.splitlines():
        # First 2 chararcters are always the status. The rest is the path.
        status, path = line[:2], line[3:]

        if staged_only:
            if status[0] != ' ':
                status = status.strip()
            else:
                secho(f"Skipping non staged change {path}", fg="black")
                continue
        else:
            status = status.strip()

        if "->" in path:
            path = path.split("->")[1].strip()
        path = Path(path.strip('"'))
        status = GitStatus(status)

        git_file_status = GitFileStatus(path, status)

        statuses.append(git_file_status)

        secho(f"File: {git_file_status.path}, Status: {git_file_status.status}")

    # Read in `iteration.json`
    with open(ITERATION_FILE) as f:
        iteraction_json = json.load(f)

    iteration = Iteration.from_dict(iteraction_json)

    secho("Iteration", bold=True)
    secho(f"Tracking {len(iteration.iterations)} blueprints", fg="white")

    filtered = [
            status for status
            in statuses
            if status.path.suffix == BLUEPRINT_EXTENSION
    ]

    secho(f"Found {len(filtered)} changed blueprints\n", bold=True)

    for index, status in enumerate(filtered):
        # secho(f"File: {status.path.stem}, Status: {status.status}", fg="white")
        # secho(f"Message: {status.message}", fg="white")


        secho(f"No. {index+1}: {status.status.message} {status.path.stem}\n", fg="white")

        with open(VERSION_FILE, 'r') as f:
            version = Version(**json.load(f))

        updated_version = update_version(version)

        try:
            custom_message = prompt("Feel free to add a custom message to your commit and tag", type=str, default="")
        except Abort:
            secho("Leaving early...")
            return

        start = style(f"Please confirm the following:\n", bold=True)
        update_iteration = style(f"- Update ", fg="white") + style(f"{ITERATION_FILE}\n", fg="cyan")
        update_warehouse = style(f"- Update warehouse version to ", fg="white") + style(f"{updated_version.version}\n", fg="cyan")
        run_command = style(f"- Run the following (stage, commit, tag) commands?\n", fg="white")

        stage = f"git add {ITERATION_FILE} {VERSION_FILE} '{str(status.path)}'"
        commit = f"git commit -m '{status.message}\n\n{custom_message}'"
        tag = f"git tag v{updated_version.version} -m '{status.message}\n\n{custom_message}'"


        stlyed_command = style(f"{stage} && {commit} && {tag}\n", fg="green")

        push = style(f"- Push to remote\n", fg="white")

        confirmation = (
            start
            + update_iteration
            + update_warehouse
            + run_command # Stage & Commit & tag
            + stlyed_command
            + push
        )

        try:
            confirmed = confirm(confirmation, default=True)
        except Abort:
            secho("Leaving early...")
            return

        if not confirmed:
            secho("It's your choice. Totally understand.\n\n")

            continue

        # 1. Update `iteration.json`
        # 2. Update the version number
        # 3. Add the changes to git
        # 4. Commit
        # 5. Tag
        # 6. Push

        with open(ITERATION_FILE, 'w') as f:
            updated = update(iteration, status)
            json.dump(asdict(iteration), f, indent=4)

        with open(VERSION_FILE, 'w') as f:
            json.dump(asdict(updated_version), f, indent=4)

        c.run(stage)

        c.run(commit)

        c.run(tag)

        c.run("git push")

    return


def update_version(version) -> Version:
    version.version = version.version +1

    return version


def update(iteration: Iteration, status: GitFileStatus) -> Iteration:
    if not status.isBlueprintFile:
        raise Exit(f"This is not the blueprint file that you are looking for. 👋 {status}")

    path = str(status.path)
    existing = iteration.iterations.get(path)

    if existing:
        iteration_number = existing.iteration

        secho(f"Found the exitistng iteration entry with iteration at {iteration_number}.")

        iteration_number += 1
    else:
        secho(f"Creating a new iteration entry for {status.path.stem}")
        iteration_number = FIRST_ITERATION_NUMBER

    blueprint_iteration_model = BlueprintIterationModel(
        status.path.stem, # name
        str(status.path), # path
        iteration_number
    )

    iteration.iterations[path] = blueprint_iteration_model


@task
def initialize_warehouse(c):
    # Guard against the cases whre we have a non empty `iteration.json` file
    if ITERATION_FILE.exists():
        # Read `iteration.json`
        with open(ITERATION_FILE, 'r') as f:
            content = f.read()

        # Make sure it's empty
        if content:
            raise Exit(f"{ITERATION_FILE} already exists!")

    # Find all blueprints under the ROOT folder
    paths = list(ROOT.rglob("*.spz2bp"))
    # Change the paths to relative paths
    paths = [ path.relative_to(ROOT) for path in paths ]

    # secho("Blueprint files", bold=True)
    # for path in paths:
    #     secho(path, fg='black')

    # Map the paths to iteration models
    iteration_models = [
        BlueprintIterationModel(
            path.stem, # name
            str(path) # path
            # iteration 1 by default
        )
        for path in paths
    ]

    # secho("Blueprint Iteration Models", bold=True)
    # for model in iteration_models:
    #     secho(model, fg='white')

    iterations = { str(model.path): model for model in iteration_models }

    # secho("The Iteration Model", bold=True)
    # secho(iterations, fg='white')

    iteration = Iteration(iterations)

    # `iteration.json` should be either empty or it does not exist yet.
    with open(ITERATION_FILE, 'w') as f:
        json.dump(asdict(iteration), f, indent=4)
