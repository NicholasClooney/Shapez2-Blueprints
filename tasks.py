import json


from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path


from click import confirm, secho, style
from invoke import Exit, task


ROOT = Path(__file__).parent
ITERATION_FILE = Path('iteration.json')


BLUEPRINT_EXTENSION = ".spz2bp"


# Extensions


# Git


class GitStatus(Enum):
    ADDED = "A"
    MODIFIED = "M"
    UNTRACKED = "??"

    @property
    def message(self) -> str:
        commit_message = {
            "A": "Add",
            "M": "Update",
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


# Iteration Related Models


@dataclass
class BlueprintIterationModel:
    name: str
    path: str # JSON serialization does not support `pathlib.Path`
    iteration: int = 1


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
def version_and_commit(c):
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
        status, path = line[:2].strip(), line[3:]

        path = Path(path.strip('"'))
        status = GitStatus(status)

        git_file_status = GitFileStatus(path, status)

        statuses.append(git_file_status)

        secho(f"File: {git_file_status.path}, Status: {git_file_status.status}", fg="black")

    # Read in `iteration.json`
    with open(ITERATION_FILE) as f:
        iteraction_json = json.load(f)

    iteration = Iteration.from_dict(iteraction_json)

    secho("Iteration", bold=True)
    secho(f"Tracking {len(iteration.iterations)} blueprints", fg="white")

    filtered = [
            status for status
            in statuses
            if status.status.value != "??" and status.path.suffix == BLUEPRINT_EXTENSION
    ]

    secho(f"Found {len(filtered)} changes (currently tracked in git)", bold=True)
    for status in filtered:
        # secho(f"File: {status.path.stem}, Status: {status.status}", fg="white")
        # secho(f"Message: {status.message}", fg="white")


        commit = f"git commit -m '{status.message}'"

        secho(f"Status: {status.status}\nFile: {status.path.stem}")

        stlyed_command = style(commit, fg="green")
        confirmation = style(f"Update {ITERATION_FILE} and run the commit command? ", fg="white") + stlyed_command

        confirmed = confirm(confirmation, default=True)

        if confirmed:
            # 1. Update `iteration.json`
            # 2. Add the json change to git
            # 3. Prepare the commit message

            updated = update(iteration, status)

            with open(ITERATION_FILE, 'w') as f:
                json.dump(asdict(iteration), f, indent=4)

            c.run(f"git add {ITERATION_FILE}")

            c.run(commit)


    return


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
        iteration_number = 0

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
