# dbdump

dbdump is a lightweight unidirectional MySQL data synchronization tool that consists of two parts:

1. `dbd_server` - a web server that monitors changes in a source database
2. `dbd_puller` - a command-line tool to pull the changes reported by `dbd_server`, updating a target database

The way it works is very simple: Any tables with an auto-updating TIMESTAMP column can be synchronized. Since making a change to a row with this type of column (almost) always ensures that the timestamp is updated when one or more columns changed, we can use it as sliding time window to determine how far behind the destination database tables are.

No additional tables or configuration is required for tracking change history state.


## dbd_server - Starting the change monitoring web server

To run the web server on the source database, use the `dbd_server` command line tool:

    usage: dbd_puller [-h] -sh HOST_OR_IP [-sP PORT] [-su USERNAME] [-sp PASSWORD]
                      -sd DATABASE -dh HOST_OR_IP [-dP PORT] -du USERNAME
                      [-dp PASSWORD] -dd DATABASE [-t table1,tableN,...]
                      [--poll-interval seconds] [-d] [--version]

    Pulls changes from a dbd_pusher server

    optional arguments:
      -h, --help            show this help message and exit

    Source:
      Source dbd_server (that changes are read from)

      -sh HOST_OR_IP, --host HOST_OR_IP
                            dbdump web server
      -sP PORT, --port PORT
                            dbdump web server port (default: 8888)
      -su USERNAME, --username USERNAME
                            dbdump username
      -sp PASSWORD, --password PASSWORD
                            dbdump password
      -sd DATABASE, --database DATABASE
                            Source database name

    Destination:
      Destination MySQL database server (that changes get written to)

      -dh HOST_OR_IP, --db-host HOST_OR_IP
                            Database server host
      -dP PORT, --db-port PORT
                            Database server port (default: 3306)
      -du USERNAME, --db-username USERNAME
                            Database user
      -dp PASSWORD, --db-password PASSWORD
                            Database password
      -dd DATABASE, --db-database DATABASE
                            Destination database name

    Sync:
      Synchronization options

      -t table1,tableN,..., --tables table1,tableN,...
                            Ordered list of tables to sync (default: all tables
                            that dbd_server supports)
      --poll-interval seconds
                            Polling interval between pull requests (if
                            unspecified, polling will be disabled)

    Misc:
      Miscallaneous options

      -d, --debug           Enable debug mode
      --version             Display version and exit
  
### dbd_server examples

Start the server on port 8888 and connect to database server host 'dbserver' as 'root' without a password:

    ./dbd_server --db-host dbserver


Start the server on port 8000, use SSL, and require HTTP authentication (as: foo/bar) for clients:

    ./dbd_server --listen-port 8000 \
                 --listen-ssl \
                 --listen-username foo \
                 --listen-password bar \
                 --db-host dbserver \
                 --db-username root \
                 --db-password secret \
                 --db-database SOURCE


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

    usage: dbd_puller [-h] -sh HOST_OR_IP [-sP PORT] [-su USERNAME] [-sp PASSWORD]
                      -sd DATABASE -dh HOST_OR_IP [-dP PORT] -du USERNAME
                      [-dp PASSWORD] -dd DATABASE [-t table1,tableN,...] [-d]
                      [--version]

    Pulls changes from a dbd_pusher server

    optional arguments:
      -h, --help            show this help message and exit

    Source:
      Source dbd_server (that changes are read from)

      -sh HOST_OR_IP, --host HOST_OR_IP
                            dbdump web server
      -sP PORT, --port PORT
                            dbdump web server port (default: 8888)
      -su USERNAME, --username USERNAME
                            dbdump username
      -sp PASSWORD, --password PASSWORD
                            dbdump password
      -sd DATABASE, --database DATABASE
                            Source database name

    Destination:
      Destination MySQL database server (that changes get written to)

      -dh HOST_OR_IP, --db-host HOST_OR_IP
                            Database server host
      -dP PORT, --db-port PORT
                            Database server port (default: 3306)
      -du USERNAME, --db-username USERNAME
                            Database user
      -dp PASSWORD, --db-password PASSWORD
                            Database password
      -dd DATABASE, --db-database DATABASE
                            Destination database name

    Sync:
      Synchronization options

      -t table1,tableN,..., --tables table1,tableN,...
                            Ordered list of tables to sync (default: all tables
                            that dbd_server supports)

    Misc:
      Miscallaneous options

      -d, --debug           Enable debug mode
      --version             Display version and exit

### dbd_puller examples

Connect to the `dbd_server` at my-server.com:8888 and sync changes to a local MySQL server on port 3306:

    ./dbd_puller --host my-server.com \
                 --port 8888 \
                 --db-host localhost \
                 --db-port 3306 \
                 --db-username root \
                 --db-password secret \
                 --db-database TARGET
