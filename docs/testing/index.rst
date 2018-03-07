.. _testing-guide:

Testing Guide
#############

Welcome to the Testing Guide for JabberCat.

About this Document
===================

This document is intended to give a quick guide for testing early JabberCat
releases. This document is **not** for you, if you are not comfortable to file
bug reports on GitHub or directly to the author.

Throughout this document, terminal commands will be suggested. Those prefixed
with ``$`` shall be executed by a normal, unprivileged user. Those prefixed
with ``#`` (usually) need root privilegues to work correctly.

.. code-block:: console

    $ echo "foo"

About testing JabberCat
=======================

The stated goals of the current round of testing are the following:

* get early feedback on the User Experience choices made in JabberCat
* allow prioritization of features based on feedback

.. warning::

    Notably, in the current state, JabberCat is not intended to be used in a
    production environment. Please consider the following:

    * data and config stored by JabberCat in this version may not be readable
      by future JabberCat versions
    * conversations may appear incomplete, messages may be missing or not be
      transmitted despite the UI giving a different appearance.


Installing and starting JabberCat
=================================

.. note::

    This guide is written with Linux in mind. No tests (at all) have been made
    on other platforms at the time of writing. If you are interested in getting
    JabberCat on a non-Linux platform, please `get in touch
    <mailto:jonas@wielicki.name>`_.

Preparations
------------

We recommend to do everthing in a fresh directory. Let’s call this directory
``jctest``. We will now clone a few repositories:

.. code-block:: console

    $ git clone https://github.com/horazont/aioxmpp
    $ git clone https://github.com/jabbercat/jclib
    $ git clone https://github.com/jabbercat/jabbercat

.. seealso::

    :mod:`aioxmpp` is the XMPP library used by JabberCat. :mod:`jclib` is the
    middle-end library between XMPP and the user interface.

Installing dependencies via distributions package managers
----------------------------------------------------------

ArchLinux
~~~~~~~~~

.. code-block:: console

    # pacman -S python-pyqt5 python-pyopenssl python-xdg python-keyring \
        python-sqlalchemy python-virtualenv

Debian/Ubuntu
~~~~~~~~~~~~~

.. code-block:: console

    # apt install python3-pyqt5 python3-pyqt5.qtwebchannel \
        python3-pyqt5.qtwebengine python3-sqlalchemy virtualenv \
        qtbase5-dev-tools python3-keyring python3-xdg python3-pyasn1 \
        python3-pyasn1-modules

(If you encounter issues when running ``make`` later, try installing
``qt5-default``, too.)

Gentoo
~~~~~~

.. code-block:: console

    # emerge -av dev-python/sqlalchemy dev-python/keyring \
	    dev-python/pyopenssl dev-python/PyQt5 dev-python/pyxdg

Fedora
~~~~~~

Sorry, no guidelines here. Feel free to recommend some.

Setting up a virtual environment
--------------------------------

.. note::

    This guide recommends the use of a `virtual Python environment
    <http://docs.python-guide.org/en/latest/dev/virtualenvs/#lower-level-virtualenv>`_.
    If you are comfortable with managing the dependencies yourself, you can skip
    this section. Skipping this section is **not** recommended for people not
    familiar with Python and PyQt5 development.

The virtual environment is created and activated using the following
commands. Make sure to select a Python interpreter with at least Python 3.5
support.

.. note::

    Please check which version of Python 3 is installed on your system with
    ``python3 --version`` and use the minor version of that. E.g. if the output
    is ``Python 3.6.4``, use ``python3.6`` in the command line below.

.. note::

    If you experience issues down the road and are re-using a virtual
    environment from a previous test (e.g. a few weeks old), try re-creating
    the environment.

    If a module is supposedly missing, definitely do try re-creating the
    environment and pay attention to the version of python.

.. code-block:: console

    $ virtualenv --system-site-packages --python python3.5 env
    $ . env/bin/activate

From this point forward, operations on python packages will happen within the
virtual environment. This is to protect your system and user python libraries
from unintended mixing with the dependencies we’re going to install.

Note that we intentionally use ``--system-site-packages``. You don’t want to
install PyQt5 via Pip, really.

Packages from PyPI
~~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ pip3 install aioopenssl aiosasl quamash
    $ (cd aioxmpp && pip install -e .)
    $ (cd jclib && pip install -e .)


Starting JabberCat
------------------

Now before we get to the interesting part, a word of warning: You are testing
absolute pre-alpha software here. As already mentioned, it may have interesting
and possibly bad bugs, which may corrupt the conversations you’re having. Do
not use this for anything important (yet). Some things aren’t entirely sorted
out yet.

Also, JabberCat will produce a whole bunch of output. This is necessary to
debug any issues you find during testing. However, it may also include your
password in readable form, especially during the initial startup of an account,
but also in general (when a reconnect is made for whatever reason).

.. note::

    The inclusion of your password only happens with aioxmpp version from
    before 2017-12-05. It took a while to fix, because the fix was not entirely
    trivial (spanning several layers), and we wanted to keep the quality of
    aioxmpp up.

    It only happens when the server only offers plaintext password
    authentication, and we don’t really have control over that. The debug logs
    include everything sent over the wire, and previously there was no way to
    reliably strip the password out of that.

    Just be careful when pasting things, and when in doubt, ask for advice.

Now, let’s build the files needed for JabberCat to run (assuming you are in the
``jctest/jabbercat/`` directory):

.. code-block:: console

    $ make

If ``make`` fails with an error related to an invocation of ``rcc`` and you are
running debian, try installing ``qt5-default``.

.. note::

    You need to have a UTF-8 locale set.

.. note::

    Make may print "failed to load emoji database" as the last line; this is
    a warning which can safely be ignored (because it comes from the process
    which builds the very emoji database; it foolishly tries to load it before
    building, non-fatally).

With that finished, you can start JabberCat with the following command:

.. code-block:: console

    $ make run-debug

This will:

* create a log file with the current timestamp where all jabbercat output goes
* make a QWebEngineView debugger listen at TCP port 1234; with a Chromium-based
  browser, you can open the debugger by navigating to `http://localhost:1234`_.


Testing notes
=============

Known issues
------------

* Sometimes, no messages are shown after joining a MUC, despite the join
  succeeding. Sometimes, not even messages sent after the join will show up.
  Please report this to a developer **while it is happening**. They will guide
  you through steps to take to debug this situation.

* There is no way to know if a conversation has received new messages while
  it’s not open; we’ll add notifications and unread-message counters to the
  list of conversations at some point.

* Similarly, handling of highlighting/mentions in MUCs is not implemented yet.

* Setting avatars, account tags and account colors isn’t implemented yet.

* The text input will be sized more reasonably at some point.

* Some kind of nickname and emoji completion suggestions will be implemented for
  the text input. Suggestions welcome.

* You will sometimes see exception tracebacks -- if they are *preceded* by a
  line starting with ``DEBUG``, do not report them (those are normal and
  verbose, indeed, but sometimes tremendously useful).

* No logging of messages to persistent storage and no access of server-side
  archives is supported yet.

Focus areas
-----------

For the early testing, there’s not really a focus. Report each and every thing
which you feel is off with the UX. If you think it may simply be a missing
feature, you can either report it (if there’s a chance we might miss it
otherwise), ask a dev in the MUC or directly (see below) or simply report it.
Issues are cheap.

Reporting issues
----------------

When reporting issues, if possible please get in contact with a developer
before filing an issue on GitHub. This is to avoid incomplete bug reports and
tedious back-and-forth, or worse, accidental and unnecessary exposure of your
private information.

To get in touch, you can:

* join our MUC at `jabbercat@conference.zombofant.net
  <xmpp:jabbercat@conference.zombofant.net?join>`_,
* directly send Jabber IMs to `jonas@wielicki.name <xmpp:jonas@wielicki.name>`_
  (adding them to the roster before sending a message is recommended, but not
  needed as long as your message is not multi-line).
* send an e-mail to `jonas@wielicki.name <mailto:jonas@wielicki.name>`_.

Of course, if you feel confident with reporting issues, feel free to `open one
at GitHub <https://github.com/jabbercat/jabbercat/issues/new>`_ right away.


Information to include in issue reports
---------------------------------------

If possible, please include the output of:

.. code-block:: console

    $ python3 -m jabbercat --version

This will print the JabberCat version, as well as the versions of a few key
dependencies and basic information about your OS. This helps with debugging.
If you don’t feel comfortable sharing any of the included information, feel
free to redact.
