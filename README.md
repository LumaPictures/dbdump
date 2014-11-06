# dbdump

dbdump is a lightweight unidirectional MySQL data synchronization tool that consists of two parts:

1. `dbd_server` - RESTful web API that sends recent db changes to `dbd_puller`.
2. `dbd_puller` - Periodically pulls changes from `dbd_server` and saves them to a database.

The way it works is very simple: Any tables with an auto-updating `TIMESTAMP` column can be synchronized. Since making a change to a row with this type of column (almost) always ensures that the timestamp is updated when one or more columns changed, we can use it as sliding time window to determine how far behind the destination database tables are.

No additional tables or configuration is required for tracking change history state.


## Installation

1. Ensure Python 2.7 and pip are installed
2. If you're on OSX, you may want to install the 'cryptography' module via macports:

    sudo port install py27-cryptography

3. Install remaining dependencies:

    sudo pip install -r requirements.txt


## dbd_server - Starting the change monitoring web server

To run the web server on the source database, use the `dbd_server` command line tool:

    usage: dbd_server [-h] [-a IP] [-P PORT] [-u USERNAME] [-p PASSWORD] [-s]
                      [--ssl-private-key FILE_PATH] [--ssl-public-key FILE_PATH]
                      --source-host HOST_OR_IP [--source-port PORT]
                      --source-username USERNAME [--source-password PASSWORD]
                      [--source-databases database1,databaseN,...] [-d]
                      [--version]

    Web server that sends changed database records to clients. Client can request
    all changed records that occurred since a specific date and time.

    optional arguments:
      -h, --help            show this help message and exit
      -d, --debug           Enable debug mode (shows more detailed logging and
                            auto-restarts web server when script files change)
      --version             Display version and exit

    Web Server:
      HTTP server that listens for dbd_puller clients.

      -a IP, --listen-address IP
                            Listener interface address (default: 0.0.0.0)
      -P PORT, --listen-port PORT
                            Listener port (default: 8888)
      -u USERNAME, --listen-username USERNAME
                            Username required for connecting HTTP clients
      -p PASSWORD, --listen-password PASSWORD
                            Password required for connecting HTTP clients
      -s, --listen-ssl      Require SSL encryption
      --ssl-private-key FILE_PATH
                            Private key file in OpenSSL format (default: ssl.key)
      --ssl-public-key FILE_PATH
                            Public key file in OpenSSL format (default: ssl.crt)

    Source Database:
      MySQL database server where changes are being monitored. All qualified
      tables must have an auto-updating TIMESTAMP column.

      --source-host HOST_OR_IP
                            Database server host
      --source-port PORT    Database server port (default: 3306)
      --source-username USERNAME
                            Database username
      --source-password PASSWORD
                            Database password
      --source-databases database1,databaseN,...
                            Databases to expose (default: all databases)

### dbd_server examples

Start the server on port 8888 and connect to database server host 'dbserver' as 'root' without a password:

    ./dbd_server --source-host dbserver --source-username root


Start the server on port 8000, use SSL, and require HTTP authentication (as: foo/bar) for clients:

    ./dbd_server --listen-port 8000 \
                 --listen-ssl \
                 --listen-username foo \
                 --listen-password bar \
                 --source-host dbserver \
                 --source-username root \
                 --source-password secret \
                 --source-database SOURCE


### Manually querying the web server

The protocol is RESTful and should be pretty easy to understand. You basically tell the web server what database and table you want changes for, asking for changes that occurred after a `since` argument (containing a date/time). You can also optionally tell it to `include_columns` or `exclude_columns` to subset your data.

Get a list of supported tables in a given database:

    http://localhost:8888/<database_name>/


Get all records modified in table 'foo' since 1/9/2014 1:23:45, only returning columns a, b, and c:

    http://localhost:8888/test/foo/?since=2014-09-01+01:23:45&include_columns=a,b,c


Get all records in a given table, but omit columns x, y, and z:

    http://localhost:8888/test/foo/?exclude_columns=x,y,z


## dbd_puller - Pulling changes from the dbd_server

To get changes from the `dbd_server` and sync them to a local database, run `dbd_puller`. You can do things like specify the order of tables to sync (if foreign key constraints come into play, or you need to subset what gets synchronized) and specify polling interval so that changes are continously synced.

Use the `dbd_puller` command line tool:

    usage: dbd_puller [-h] --source-host HOST_OR_IP [--source-port PORT]
                      [--source-username USERNAME] [--source-password PASSWORD]
                      --source-database DATABASE [--source-timeout SECONDS]
                      --dest-host HOST_OR_IP [--dest-port PORT] --dest-username
                      USERNAME [--dest-password PASSWORD] --dest-database DATABASE
                      [-t table1,tableN,...]
                      [-x table1.column1,tableN.columnN,...]
                      [--poll-interval seconds] [-d] [--version]

    Pulls changes from a dbd_pusher server

    optional arguments:
      -h, --help            show this help message and exit
      -d, --debug           Enable debug mode
      --version             Display version and exit

    Source:
      Source dbd_server (that changes are read from)

      --source-host HOST_OR_IP
                            dbdump web server
      --source-port PORT    dbdump web server port (default: 8888)
      --source-username USERNAME
                            dbdump username
      --source-password PASSWORD
                            dbdump password
      --source-database DATABASE
                            Source database name
      --source-timeout SECONDS
                            Seconds to wait before timing out connection attempt
                            (default: 15)

    Destination:
      Destination MySQL database server (that changes get written to)

      --dest-host HOST_OR_IP
                            Database server host
      --dest-port PORT      Database server port (default: 3306)
      --dest-username USERNAME
                            Database user
      --dest-password PASSWORD
                            Database password
      --dest-database DATABASE
                            Destination database name

    Sync:
      Synchronization options

      -t table1,tableN,..., --tables table1,tableN,...
                            Ordered list of tables to sync (default: all tables
                            that dbd_server supports)
      -x table1.column1,tableN.columnN,..., --exclude-columns table1.column1,tableN.columnN,...
                            Columns to exclude from synchronization
      --poll-interval seconds
                            Polling interval between pull requests (if
                            unspecified, polling will be disabled)

### dbd_puller examples

Connect to the `dbd_server` at my-server.com:8888 and sync changes to a local MySQL server on port 3306:

    ./dbd_puller --source-host my-server.com \
                 --source-port 8888 \
                 --dest-host localhost \
                 --dest-port 3306 \
                 --dest-username root \
                 --dest-password secret \
                 --dest-database TARGET

## Caveats

This synchronization process is simple, and not perfect. It should suit our needs, but it’s still a work in progress. Here’s some caveats to be aware of:

* Doesn’t synchronize DELETEs. Just works for INSERT and UPDATE.
* The dbd_puller and dbd_server processes may die (from connection timeouts or other unexpected exceptions), and should be monitored with something like supervisor.
* There’s an option to encrypt traffic by enabling SSL on the web server, but it’s untested.

## Future Plans

* Synchronize DELETEs (periodically) by testing set difference of primary keys.
* Allow the dbd_server to be mounted as a WSGI endpoint. This requires creating environment variable equivalents to the command line arguments, since arguments can’t be passed to a WSGI script.
