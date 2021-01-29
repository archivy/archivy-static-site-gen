from pathlib import Path
from shutil import rmtree, copytree
from sys import exit

import click
from bs4 import BeautifulSoup
from flask import render_template
from flask_login import UserMixin

from archivy import app
from archivy.data import get_item, get_items
from archivy.forms import DeleteDataForm

class LoggedInUser(UserMixin):
    is_authenticated = True

def process_render(route, **kwargs):
    resp = render_template(route, **kwargs, current_user=LoggedInUser())
    soup = BeautifulSoup(resp)
    for form in soup.find_all("form"):
        form.decompose()
    return str(soup)

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
    with app.test_request_context():
        items = get_items(structured=False)
        for i in items[:10]:
            with (output_path / f"{i['id']}.html").open("w") as f:
                f.write(process_render("dataobjs/show.html", dataobj=i, form=DeleteDataForm(), current_path=i["dir"], dataobjs=get_items()))

    

