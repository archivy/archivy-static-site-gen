# archivy-static-site-gen

`archivy-static-site-gen` is a plugin for [Archivy](https://github.com/archivy) that allows you to build a static, view-only version of your data, that you can then deploy on any static hosting platform like GitHub Pages or Netlify.

```
$ archivy static-site --help

Usage: archivy static-site [OPTIONS] COMMAND [ARGS]...

  Plugin to generate a static website from your archivy data

Options:
  --help  Show this message and exit.

Commands:
  build  Builds a _site/ directory with HTML generated from archivy...
  omit   Allows you to specify filenames you'd like to ignore during the...
```

## Installation

Requires a working installation of [Archivy](https://github.com/archivy/archivy):

`pip install archivy-static-site-gen`

## Usage

- Build your content with `archivy static-site build` and then host the generated files as you wish to.
- Remove files from the build with `archivy static-site omit`


## Todo

- Add static search functionality
- Be able to omit entire directories in one go.
- Option to provide a description of the wiki on the homepage.
- Code improvements
- Potential speed enhancements.
