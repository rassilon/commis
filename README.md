## WHAT

Commis is a [Django](http://djangoproject.com) implementation of [Chef
Server](http://wiki.opscode.com/display/chef/Chef+Server). It's currently
compatible with Django 1.2 through 1.4, and thus has the same dependencies as
those releases:

* Python 2.5 or newer
* A relational database engine (this includes the ships-with-Python SQLite)

On top of that, Commis requires a handful of other pure-Python libraries, such
as PyChef, Celery and PyParsing.


## WHY

There are a number of reasons you may want to deploy Commis instead of the
standard Chef Server implementation or using Opscode's hosted service:

### Simpler deployment

**Chef Server requires many components & runtimes in addition to Ruby**:
RabbitMQ (and thus Erlang), CouchDB (also Erlang), Solr (Java), and `gecode`.
Installation quickly gets complicated on non-Ubuntu platforms such as CentOS or
Fedora (have fun finding up to date `gecode` RPMs or waiting an hour for it to
compile!).  Managing and supporting the different components is also a large
hurdle for users who just want to get started, regardless of platform.

Conversely, in its most basic form, **Commis relies purely upon Python
libraries** -- the embedded SQLite for databasing, Whoosh for text indexing,
and Celery for queuing (which can function without an actual queue when not
needed.)

Furthermore, **you can easily replace these components when necessary, and with
whatever backends you want**.  SQLite crumbles with more than a few concurrent
users? Use Postgres or MySQL (or Oracle or ...). Need non-eager background
jobs? Use any [Celery](http://celeryproject.org/)-supported backend (like
Redis), you're not limited to RabbitMQ. Ditto for text indexing -- anything
[Haystack](http://haystacksearch.org/) supports is fair game.

### Improved hackability

As a third party solution, Commis is free to innovate and add experimental
features that aren't suitable for the official Chef Server project. This
includes things like major UI changes for the web interface and flexible policy
backends that are designed be be altered to suit your needs.

For example, not everybody is able or willing to treat their Chef Server as the
single source of truth -- imagine being able to plug-in or sync your
pre-existing LDAP server or Clusto database such that your Chef recipes see the
data as regular attributes, or even as dynamically managed node or client
entries. And this is just one example.

### Python interoperability

Mostly a sub-case of the above -- Commis, being Python, is a great fit for
shops with pre-existing Python systems or Python deployment experience.
Learning Ruby to write Chef manifests is one thing; becoming comfortable
deploying a complex Ruby web-app is another entirely. With Commis, you might
not have to.


## HOW

Here's how to get started hacking on or evaluating Commis. It assumes you want
to run off the abovementioned pure-Python default stack; to move away from
those defaults, you'll just need to install the additional components you want
and modify `commis/settings.py` appropriately.

### Installation

On the system acting as Chef Server, get Commis installed and running:

* Get Commis:
    * Clone, download tarball, etc.
* (Optional but strongly recommended) Create a
  [virtualenv](http://www.virtualenv.org) and activate it.
* Get dependencies:
    * `pip install -r requirements.txt`
* Put Commis on your PYTHONPATH (some settings files need to import
  `commis.<x>`):
    * `pip install -e .`
* Install DB schema:
    * `python commis/manage.py syncdb`
    * By default, this creates a SQLite database in `commis/commis.db`. As
    always, you can change this in `commis/settings.py`.
    * It will prompt you for a new admin user -- make sure you keep track of
    this as it's how you will login to the Web UI and manage everything.
* Start it up to make sure things work:
    * `python commis/manage.py runserver 0.0.0.0:8000`
        * Obviously you may alter the port number to taste.
        * Commis currently runs both the Web UI and the REST API on the same
        Web worker/port. API requests go to `/api/*` while everything else is
        assumed to be part of the regular Web app. By contrast, Chef Server
        runs the API off port 4000 and the Web UI off 4040, by default.
    * Hit up `http://localhost:8000/` (obviously substituting `localhost` for
    the server address if you're using a nonlocal system) and make sure you can
    log in as your admin user and click around.

### Client/key management

You now have a working Commis install, but you need to do some Chef client/key
management in order for Chef clients such as `chef-client` or `knife` to use
the server. Here's a conceptual overview:

* Chef "clients" are entities allowed to connect to the Chef server API and
  manipulate/query the database. They are **distinct** from "users" which are
  solely used to handle authentication in the Web application itself (in this
  case, users are regular Django user objects.)
* Clients are really just an association between a name and an RSA key pair
  (think SSH keys -- two chunks of text, one public and one private) which is
  then stored in the Chef server DB with metadata about what privileges it has.
* There are three kinds of Chef clients:
    * **Admin** clients have full privileges and are analogous to SQL database
    admin or root users. They're used to grant actual humans access to the Chef
    server, typically via the `knife` CLI tool.
    * **Node** clients represent a given Chef-managed system or "node", and are
    analogous to SQL per-database users. They can only manipulate their related
    Node object and its data.
    * **Validator** clients are semi-privileged -- they're used solely to
    create new node clients on the fly.
* Thus, the workflow you need looks like this:
    * Ensure an admin client exists, so you can use it to manage the server via
    `knife`.
        * Chef is generally oriented around `knife` management -- the Web UI is
        more limited, at least at the moment. Theoretically, a richer Web
        interface could remove any need for a command-line admin client.
    * Ensure a validator client exists and that its private key file is in a
    known location.
    * New Chef-managed systems then obtain a temporary copy of the validator
    key (e.g. via `scp` or authenticated download) and use it with
    `chef-client` to create new node clients/keys for themselves.

#### Actual client/key HOWTO

That's a lot to digest, but hopefully we distilled it enough to be clear.
Here's the actual steps to take with your new Commis server to get it ready for
node clients:

* Make an admin client with `python commis/manage.py commis_client --admin
<name>`.
    * Here, and elsewhere, replace `<name>` with your desired client name or
    username. It could, for example, match your Django-level superuser account
    name -- but doesn't have to.
    * This will create a file in your working directory named `<name>.pem` --
    this is your private key, so keep it secret!
* Make the validator client with `python commis/manage.py commis_client
  --validator`.
    * This generates `validator.pem` in your working directory.
* Copy both `.pem` files somewhere persistent that you will remember, such as
  `~/.chef/` or `/etc/chef/`.
* Select a system to use for managing your Commis server via `knife` -- could
  be the Commis server itself, or your local workstation, doesn't matter.
* On that system, get the `chef` Ruby gem installed (e.g. `gem install chef`)
  and copy down the two `.pem` files you created above (if you selected a
  different system as the workstation.) A good location may be `~/.chef/` as
  that's where Knife defaults to storing its config files and so forth.
* Run `knife configure`. (Note: **not** `knife configure -i` as many
  vanilla tutorials say. We've already generated your client key above.) It'll
  prompt you for the following:
  * The location of the conf file to generate. Probably safest to use the
  default, `~/.chef/knife.rb`.
  * The Chef Server URL. This will be the hostname or IP of your Commis server,
  plus port 8000, and -- **this is a departure from regular Chef Server** -- a
  trailing `/api`.
      * For example, if you are using the Commis system itself as your
      management host, simply enter `http://localhost:8000/api`.
  * The client name. This is the new admin user you just made above, i.e.
  `<name>`.
  * The validator name. This is `validator`.
  * The validator key path. Depending on where you moved that to, give the path
  here, e.g. `~/.chef/validator.pem`.
  * A Chef repository path. You can leave this blank for now.
* Phew! That should have created `~/.chef/knife.rb` (or whatever you told it to
  use) which contains all these answers. Assuming you answered honestly re: the
  locations of the `.pem` files, you're all set.
* Test out `knife`: make sure your runserver is still active, and execute
  `knife client list`. It should spit back the two clients you just made,
  `<name>` and `validator`.

### Running cookbooks on your servers

At this point, you've got Commis running and can manage/query it via `knife`.
The next step is to do actual work: run some cookbooks on a target server/node!

#### Uploading cookbooks

To run cookbooks, you must first get those cookbooks into Commis. `chef-client`
runs expect to get all their cookbooks/recipes/etc from the server. Get some
cookbooks, either ones you already have, or quickly whip up a new one. We'll
use a trivial test cookbook:

    .
    └── testcookbook
        └── recipes
            └── default.rb

where `default.rb` just looks like this:

    log "Hello world!"

Get that `testcookbook` directory onto your `knife` system, enter its parent directory, and execute:

    knife cookbook upload -o . testcookbook

(You could skip the "enter its parent directory" step, and simply point to said parent directory as the arg to the `-o` flag. Your call.)

This should complete successfully, and you can verify it by visiting the Web UI
and viewing the Cookbooks tab, or running `knife cookbook list`.

#### Executing on a new node

Almost there now. Locate or create a system you're comfortable experimenting
on. Install Chef there (e.g. `gem install chef`, as above re: your management
workstation.) Then:

* Copy validation key to that system
* Obtain the necessary parameters to run `chef-client` against your Commis
  server, which can either be used as CLI flags, or go into a `client.rb`
  config file:
  * Path to that validation key you just copied, e.g. `/etc/chef/validator.pem`
  * Path to desired new client key, e.g. `/etc/chef/<hostname>.pem`.
    * You'll use this path for both initial & "real" `chef-client` runs -- it
    will create the file initially, then load + use it in subsequent
    invocations.
  * Server URI: same as above for Knife,
  `http://<commis-server-hostname>:8000/api`.
* Execute `chef-client` -- it should create a new node client for itself, named
  after your system's hostname, then run an empty run list.
* Verify that it's now listed on the server with `knife node list` back on your
  workstation, or via the web UI.
* Update its run list to include `"testcookbook"`, again either via knife
  (`knife node run_list add <hostname> testcookbook`) or the Web UI's edit
  form.
    * If using the Web UI, you can simply drag the "testcookbook" box from the
    lower left, into the right hand side. Then click "Edit Node" and you're
    done.
* Re-run `chef-client` -- it should print out your "Hello world!" log entry in
  the middle of its run.
* If so, you're done! Add more cookbooks, tweak run lists, and go to town.
