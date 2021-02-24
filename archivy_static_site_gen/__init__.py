from json import dumps
from pathlib import Path
from shutil import rmtree, copytree
from sys import exit

from bs4 import BeautifulSoup
import click
import frontmatter
from flask import render_template
from flask_login import UserMixin

from archivy import app
from archivy.data import get_item, get_items, Directory, get_data_dir
from archivy.forms import DeleteDataForm, NewFolderForm, DeleteFolderForm

SEARCH_HTML = """
    <input type="text" id="searchBar" placeholder="Search wiki">
    <ul id="searchHits"> </ul>
    <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/lunr@2.3.8/lunr.min.js"></script>
    <script>
        let index, titles;
        async function loadIndexAndTitles() {
            let fetchIndex = await fetch("/search-index.json", { headers: { "content-type": "application/json"}});

            if (fetchIndex.ok)
            {
                let unparsedIndex = await fetchIndex.json();
                index = lunr.Index.load(unparsedIndex);
            }
            let fetchTitles = await fetch("/titles.json", { headers: { "content-type": "application/json"}});
            if (fetchTitles)
            {
                titles = await fetchTitles.json();
            }
        }

        function appendHit(hit, hitsDiv)
        {
            if (hit["score"] > 2.5)
            {
                let hitLi = document.createElement("li"); 
                let a = document.createElement("a");
                a.href = `/dataobj/${hit["ref"]}`;
                a.textContent = titles[hit["ref"]];
                hitLi.append(a);
                hitsDiv.append(hitLi);
            }
        }

        window.onload = loadIndexAndTitles();
        let input = document.getElementById("searchBar");
        let hitsDiv = document.getElementById("searchHits");
        input.addEventListener("input", async function(e) {
            hitsDiv.innerHTML = ""; 
            index.search(input.value).slice(0, 5).map((hit) => appendHit(hit, hitsDiv));
        })

    </script>
"""

display_post = lambda post: "omit" not in post.metadata or not post["omit"]


class LoggedInUser(UserMixin):
    is_authenticated = True


def process_render(route, name, **kwargs):
    """Processes template render by wrapping with some defaults"""
    resp = render_template(route, current_user=LoggedInUser(), view_only=1, **kwargs)
    if name:
        # TODO: fix this because there can be a problem if the user
        # has an h3 with Archivy in one of their notes (using bs4 for this is not an option because it's much slower)
        resp = resp.replace("<h3>Archivy</h3>", f"<h3>{name}</h3>")
    return resp.replace("?path=", "dirs/")


def create_lunr_index(documents):
    """Creates and configures a search index for the wiki."""
    from lunr.builder import Builder
    from lunr.stemmer import stemmer
    from lunr.trimmer import trimmer
    from lunr.stop_word_filter import stop_word_filter

    builder = Builder()
    builder.pipeline.add(trimmer, stop_word_filter, stemmer)
    builder.search_pipeline.add(stemmer)
    builder.metadata_whitelist = ["position"]
    builder.ref("id")
    fields = [
        {"field_name": "title", "boost": 10},
        {"field_name": "body", "extractor": lambda doc: doc.content},
    ]
    for field in fields:
        builder.field(**field)
    for document in documents:
        builder.add(document)
    return builder.build()


def gen_dir_page(
    directory: Directory, output_path: Path, parent_dir: Path, dataobj_tree, wiki_name
):
    """Generates directory listing page recursively."""
    new_dir_path = output_path / parent_dir / directory.name
    new_dir_path.mkdir()

    with (new_dir_path / "index.html").open("w") as f:
        parent_path = str(parent_dir.relative_to(output_path))
        if parent_path == ".":
            parent_path = ""
        f.write(
            process_render(
                "home.html",
                name=wiki_name,
                dir=directory,
                title=f"{parent_path}{directory.name}",
                current_path=f"{parent_path}/{directory.name}/",
                new_folder_form=NewFolderForm(),
                delete_form=DeleteFolderForm(),
                dataobjs=dataobj_tree,
            )
        )

    for child_dir in directory.child_dirs.values():
        gen_dir_page(child_dir, output_path, new_dir_path, dataobj_tree, wiki_name)


def strip_hidden_data(directory: Directory):
    """Removes data that was specified to be omitted from the build."""
    directory.child_files = list(filter(display_post, directory.child_files))
    for subdir in list(directory.child_dirs.keys()):
        stripped_subdir = strip_hidden_data(directory.child_dirs[subdir])
        if not stripped_subdir:
            directory.child_dirs.pop(subdir)
        else:
            directory.child_dirs[subdir] = stripped_subdir
    if (
        directory.child_files or directory.child_dirs
    ):  # only display directories that have data.
        return directory
    return None


@click.group()
def static_site():
    """Plugin to generate a static website from your archivy data"""
    pass


@static_site.command()
@click.option(
    "--overwrite", help="Overwrite _site/ output directory if it exists", is_flag=True
)
@click.option(
    "--wiki_desc",
    type=click.Path(exists=True),
    help="Pass an (optional) HTML file of which the contents will be displayed at the top of the homepage of the wiki, acting as a description.",
)
@click.option("--wiki_name", type=str, help="Name of your wiki")
def build(overwrite, wiki_desc, wiki_name):
    """Builds a _site/ directory with HTML generated from archivy markdown."""
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

    dataobj_dir = output_path / "dataobj"
    dataobj_dir.mkdir()
    with app.test_request_context():
        dataobj_tree = strip_hidden_data(get_items())
        if not dataobj_tree:
            click.echo("No data found.")
            return
        items = list(filter(display_post, get_items(structured=False)))
        index = create_lunr_index(items)
        with (output_path / "search-index.json").open("w") as f:
            f.write(dumps(index.serialize()))
        # we need to store an association between id -> title, because the search engine only returns the id
        # without the title of the item
        titles = {}
        for post in items:
            titles[post["id"]] = post["title"]
            (dataobj_dir / str(post["id"])).mkdir(exist_ok=True)
            with (dataobj_dir / str(post["id"]) / "index.html").open("w") as f:
                f.write(
                    process_render(
                        "dataobjs/show.html",
                        name=wiki_name,
                        dataobj=post,
                        form=DeleteDataForm(),
                        current_path=post["fullpath"],
                        dataobjs=dataobj_tree,
                        title=post["title"],
                    )
                )

        with open(output_path / "titles.json", "w") as f:
            f.write(dumps(titles))
        with (output_path / "index.html").open("w") as f:
            home_dir_page = process_render(
                "home.html",
                name=wiki_name,
                new_folder_form=NewFolderForm(),
                delete_form=DeleteFolderForm(),
                dir=dataobj_tree,
                dataobjs=dataobj_tree,
                title="Home",
            )
            customization = (
                """
                <p><small>Powered by <a href="https://archivy.github.io" target="_blank">Archivy</a> and its <a href="https://github.com/archivy/archivy-static-site-gen">static site generator</a>.</small></p>
            """
                + SEARCH_HTML
            )
            modified_home = BeautifulSoup(home_dir_page, features="html.parser")
            if wiki_desc:
                with open(wiki_desc, "r") as desc:
                    customization = desc.read() + customization
            inserted_html = BeautifulSoup(customization, features="html.parser")
            modified_home.select_one("#files").insert_before(inserted_html)
            f.write(str(modified_home))

        directories_dir = output_path / "dirs"
        directories_dir.mkdir()
        with (directories_dir / "index.html").open("w") as f:
            f.write(home_dir_page)
        for child_dir in dataobj_tree.child_dirs.values():
            gen_dir_page(
                child_dir, directories_dir, directories_dir, dataobj_tree, wiki_name
            )


@static_site.command()
@click.argument("files", type=click.Path(), nargs=-1)
@click.option(
    "--reverse",
    help="Undo ignoring of certain data when building.",
    is_flag=True,
)
def omit(files, reverse):
    """Allows you to specify filenames you'd like to ignore during the build."""
    with app.app_context():
        for path in files:
            cur_path = Path(path)
            if path.endswith(".md") and cur_path.resolve().is_relative_to(
                get_data_dir()
            ):
                try:
                    curr_data = frontmatter.load(path)
                    curr_data["omit"] = not reverse
                    with open(cur_path, "w", encoding="utf-8") as f:
                        f.write(frontmatter.dumps(curr_data))
                except:
                    click.echo(f"Preferences for {path} could not be saved.")
    if reverse:
        click.echo("Specified files will no longer be ignored.")
    else:
        click.echo("Specified files will now be ignored during build.")
