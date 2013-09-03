# AttendMap

Some cool stuff. More info coming soon :)


## Usage

Start by cloning this repository:

    git clone https://github.com/rshk/attendmap.git

Then, configure the application:

    cd attendmap/attendmap
    cp settings.example.py settings.py
    editor settings.py

(you will need Twitter application keys and a valid geonames username)

Then, install it:

    cd ..
    python setup.py install

To see what you can do:

    python -m attendmap help


## Normal execution

Usually, you'll spanw a process like this:

    python -m attendmap loop

And then export the data periodically from another process:

    python -m attendmap export json


## Debugging shell

To launch a shell for debugging (with all the functions contained
in the package already loaded in the current scope):

    ipython -i -m attendmap shell


## Testing

Tests are coming soon, anyways you'll just have to run:

    python setup.py test

(or install py.test and run it on the project..)


## Previewing on a map

If you want to show your tweets on a map, just:

    cd map_preview
    ./update.sh
    ./serve.sh

Then visit http://127.0.0.1:8000
