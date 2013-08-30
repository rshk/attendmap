"""This can be used for running an interactive shell::

    ipython -i -m attendmap shell

"""

import sys

command_help = """
Commands:

    update
        Updates tweets in the database by querying the API

    geolocate [--all]
        Update geolocation information for new tweets (all tweets)

    loop <time (s)>
        Continuously update/geolocate tweets, then sleep for a while.
        Default time is 5 minutes.

    export { <format> | help } [--all]
        Export the tweets data in the specified format. Only tweets with
        geographical information are exported (if --all is specified all
        tweets are exported).

    shell
        Used to launch an interactive shell, using ipython.
        Just run: ``ipython -i get_tweets.py shell``

    help
        Show this help message
"""


if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = 'help'

    args = sys.argv[2:]

    if command == 'help':
        print(command_help)
        sys.exit()

    elif command == 'shell':
        ## Import everything, for interactive use.
        from . import *

    elif command == 'update':
        from . import scan_new_tweets
        scan_new_tweets()

    elif command == 'geolocate':
        from . import geolocate_tweets
        geolocate_tweets('--all' not in args)

    elif command == 'export':
        from . import exporters

        try:
            fmt = args[0]
            if fmt == 'help':
                # Trick to trigger help
                raise IndexError

        except IndexError:
            print("Supported formats: {}".format(' '.join(exporters.keys())))

        else:
            if fmt in exporters:
                export_all = '--all' in args
                print(exporters[fmt](export_all=export_all))

            else:
                raise ValueError("Unsupported format: {}".format(fmt))

    elif command == 'loop':
        import time
        from . import scan_new_tweets, geolocate_tweets
        try:
            sleep_time = int(args[0])
        except:
            sleep_time = 5 * 60
        while True:
            scan_new_tweets()
            geolocate_tweets()
            print("Sleeping {} seconds..".format(sleep_time))
            time.sleep(sleep_time)

    else:
        raise ValueError("Unknown command {}".format(command))
