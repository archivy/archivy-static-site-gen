from pathlib import Path
from shutil import rmtree, copytree
from sys import exit

import click
from bs4 import BeautifulSoup
from flask import render_template
from flask_login import UserMixin

from archivy import app
from archivy.data import get_item, get_items, Directory
from archivy.forms import DeleteDataForm, NewFolderForm, DeleteFolderForm

class LoggedInUser(UserMixin):
    is_authenticated = True

def process_render(route, **kwargs):
    resp = render_template(route, **kwargs, current_user=LoggedInUser())
    soup = BeautifulSoup(resp)
    removed = [
        lambda tag: tag.name == "form",
        lambda tag: tag.get("class") == ["btn"]
    ]
    for criteria in removed:
        for tag in soup.find_all(criteria):
            tag.decompose()
    for tag in soup.find_all(lambda tag: tag.name == "a" and tag.parent.get("class") == ["dir"]):
        tag["href"] = tag["href"].replace("?path=", "//dirs")
    return str(soup)

def gen_dir_page(directory: Directory, output_path: Path, parent_dir: Path, dataobj_tree):
    new_dir_path = (output_path / parent_dir / directory.name)
    new_dir_path.mkdir()

    with (new_dir_path / "index.html").open("w") as f:
        f.write(process_render("home.html",
            dir=directory,
            title=f"{parent_dir.relative_to(output_path)}{directory.name}",
            current_path=f"{parent_dir.relative_to(output_path)}{directory.name}",
            new_folder_form=NewFolderForm(),
            delete_form=DeleteFolderForm(),
            dataobjs=dataobj_tree
            )
        )

    for child_dir in directory.child_dirs.values():
        gen_dir_page(child_dir, output_path, new_dir_path, dataobj_tree)

@click.group()
def static_site():
    pass

@static_site.command()
@click.option("--overwrite", help="Overwrite _site/ output directory if it exists", is_flag=True)
def build(overwrite):
    output_path = Path().absolute() / "_site"
    if output_path.exists():
        if overwrite:
            rmtree(output_path)
        else:
            click.echo("Output directory already exists.")
            exit(1)

    output_path.mkdir()

    app.config["SERVER_NAME"] = "localhost:5000"
    copytree(app.static_folder, (output_path / "static"))

    dataobj_dir = output_path / "dataobjs"
    dataobj_dir.mkdir()
    with app.test_request_context():
        dataobj_tree = get_items()
        items = get_items(structured=False)
        for i in items[:10]:
            with (dataobj_dir / f"{i['id']}.html").open("w") as f:
                f.write(process_render("dataobjs/show.html", dataobj=i, form=DeleteDataForm(), current_path=i["dir"], dataobjs=dataobj_tree))

    
        with (output_path / "index.html").open("w") as f:
            home_dir_page = process_render("home.html", new_folder_form=NewFolderForm(), delete_form=DeleteFolderForm(), dir=dataobj_tree)
            f.write(home_dir_page)

        directories_dir = output_path / "dirs"
        directories_dir.mkdir()
        with (directories_dir / "index.html").open("w") as f:
            f.write(home_dir_page)
        for child_dir in dataobj_tree.child_dirs.values():
            gen_dir_page(child_dir, directories_dir, directories_dir, dataobj_tree)