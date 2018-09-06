import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="edp_redy",
    version="0.0.1",
    author="Abílio Costa",
    author_email="amfcalt@gmail.com",
    description="Unofficial python module for EDP re:dy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/abmantis/edo_redy_py.git",
    packages=setuptools.find_packages(),
    install_requires=[
        'aiohttp',
        'async_timeout',
        'datetime'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],

)
