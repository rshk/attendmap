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

    export { <format> | help } [--all] [--latest]
        Export the tweets data in the specified format.

        Only tweets with associated coordinates are exported, unless
        --all is specified.

        If the --latest flag is specified, only the most recent location
        for each user will be exported.

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
        from . import serializers, export_tweets

        if (len(args) < 1) or (args[0] == 'help'):
            print("Supported formats: {}".format(' '.join(serializers.keys())))

        else:
            fmt = args[0]
            if fmt in serializers:
                require_coordinates = '--all' not in args
                only_latest = '--latest' in args
                serializer = serializers[fmt]
                tweets = export_tweets(
                    require_coordinates='--all' not in args,
                    only_latest='--latest' in args)
                print(serializer(tweets))

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
