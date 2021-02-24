from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt', encoding='utf-8') as f:
    all_reqs = f.read().split('\n')
    install_requires = [x.strip() for x in all_reqs]

setup(
    name='archivy_static_site_gen',
    version='0.2.1',
    author="Uzay-G",
    author_email="halcyon@disroot.org",
    description=(
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
    ],
    packages=find_packages(),
    install_requires=install_requires,
    entry_points='''
        [archivy.plugins]
        static-site=archivy_static_site_gen:static_site
    '''
)
