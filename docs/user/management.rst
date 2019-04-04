.. _management-chapter:

Course and Assignment Management
========================================
The :fa:`cog` button next to courses or assignments is visible to all users with the right
permissions to manage courses or assignments. Clicking this button shows the corresponding
management page.

Additionally, clicking on the name of a course results in an overview of its assignments and
still allows to click the :fa:`cog` button on the bottom right to show the management page.

.. _course-management:

Course Management
-------------------
The first tab of the course management page, *Members*, displays a list of all
users (students, teachers and other roles) that are *enrolled* in the
course. The role of users can be changed here and new users can be added to the
course.

.. note::

    Course management is done in your learning management system if the course
    is connected, however managing roles and permissions is still done in
    CodeGrade.

The second tab, *Permissions*, shows an overview of all roles and their specific
permissions. Existing roles can be altered and completely new roles can be added
via the dialog on the bottom of the page. More information about the specific
course permissions can be found in the
:ref:`permissions chapter <permissions-chapter>`.

The third tab, *Groups*, shows all group sets of the course. Here you create,
delete and can edit the minimum and maximum size of group sets. Group sets are a
key concept for group assignments in CodeGrade, more information about them can
be found in the :ref:`groups chapter <groups-chapter>`.

The fourth tab, *Snippets*, shows all course-wide snippets in this course. These
course snippets can be set up by the teacher and can be used by all graders
grading in the course. These snippets are always in addition to the graders'
personal snippets and are indicated with the :fa:`books` icon.

Creating a new Course
~~~~~~~~~~~~~~~~~~~~~~
Specific :ref:`site permissions <site-permissions>` are required to create a
course, usually this can be done only be site administrators. If these
permissions are set, a course can be created by navigating to the courses menu
and clicking the :fa:`plus` icon. The name for the new course can then be given.

.. _assignment-management:

Assignment Management
----------------------
Clicking the :fa:`cog` button next to a specific assignment shows the assignment
management page. Usually all teachers and course designers can manage
courses and assignments.

.. _manage-assignment-state:

Assignment State
~~~~~~~~~~~~~~~~~~~
Three assignment states are available and can be set on the top right:

* :fa:`eye-slash` **Hidden** state: the assignment is invisible to students.
* :fa:`clock-o` **Open** state: the assignment is visible to students and
  students can hand in submissions before the deadline.
* :fa:`check` **Done** state: the assignment is visible to students and grading
  is finished.

General
~~~~~~~~
In this tab you can edit basic settings, as the assignment name and
deadline, but also some more advanced settings.

CGIgnore File
++++++++++++++
The CGIgnore file acts as a *filter* to all submissions. It is formatted exactly
like the common ``.gitignore`` files.  All files noted in the CGIgnore are ought
to be excluded from submissions (e.g. no ``.tex`` LaTeX source files but only
the PDF file).  Students that try to hand in a submission with excluded files
get a warning and are given the option to cancel the submission, continue the
submission but delete the excluded file or continue the submission and include
the excluded file.

.. warning::

    Ignored files **can** be submitted if a student chooses to do so, however a
    warning is always shown.

Files to be excluded are pattern matched with the entries in the CGIgnore
file. Literal filenames can be given or an ``*`` (asterisk) can be used as
wildcard (e.g. ``*.tex`` will exclude all files with the ``.tex`` extension). A
more strict wildcard is the ``?`` (question mark) which can be used to match
exactly one character (e.g. ``assignment?.py`` will exclude all Python files
that start with assignment and are followed by one character like
``assignment1.py``). All entries in the CGIgnore file should be on new lines.

Group assignment
++++++++++++++++++
Here you can select which group set to use for this assignment. When a group set
is selected the assignment becomes a group assignment. Group sets are a
key concept for group assignments in CodeGrade, more information about them can
be found in the :ref:`groups chapter <groups-chapter>`.

Uploading Submissions
+++++++++++++++++++++++
Submissions can be uploaded via the assignment management page too. Using the *Upload submission* tool submissions can be uploaded as
any requested user: hand in submissions for students or hand in as administrator by selecting a user via the search bar.

.. _upload-blackboard-zip:

Uploading Blackboard Archives
+++++++++++++++++++++++++++++++
It is possible to combine CodeGrade with the Blackboard learning management
system: handing in is done via Blackboard and grading and presenting feedback
via the stand-alone CodeGrade application. After exporting the submissions on
Blackboard (see Blackboard documentation
`here <https://help.blackboard.com/Learn/Instructor/Assignments/Download_Assignments>`__),
the downloaded archive can be uploaded using Blackboard Zip tool in CodeGrade.

By uploading this archive, CodeGrade will add all students' corresponding
CodeGrade accounts to the course and link their submissions correctly.  If a
student does not yet have a CodeGrade account, a new account will be created.

.. warning::

    BlackBoard uploading is an experimental feature that was tested working with
    BlackBoard 9, if an error occurs please contact us at help@codegra.de.

Graders
~~~~~~~~~
In this tab you can edit all settings regarding graders, like dividing and
setting up notifications for them.

Dividing Submissions
+++++++++++++++++++++
To randomly and automatically assign graders to all submissions the Divide
Submission feature on the assignment management page can be used. A list of all
graders is displayed and after selecting the wanted graders weights can be given
to affect the workload per grader. The resulting percentage is the percentage of
submissions the grader will be randomly assigned to. Newly submitted submissions
are automatically assigned to graders after dividing is performed.  Dividing
submissions is consistent, so new submissions will get assigned to the same
teaching assistant.

Manually assigning submissions is possible via the submission list, by selecting
the grader using the 'Assigned to' dropdown dialog.

It is also possible to link the divisions and assignees of multiple
assignments. To do this you can select a parent assignment in the selector below
the weights of the graders. When an assignment is connected to another
assignment, the child assignment copies the settings and assignees of the parent
assignment. After linking, the division settings of the parent and the child are
frozen. Multiple assignments can be linked to the same parent, however a parent
cannot be linked to another assignment as a child.

When a student submits to a child or parent assignment CodeGrade tries to assign
the student to the same assignee as in other assignments. It does this by first
copying the assignee of the parent assignment for the submitting student, or if
this is not possible selecting the most common assignee in the children
assignments.

.. note::

    When teachers manually assign themselves, weights are not updated to reflect
    this.

Finished Grading and Notifications
+++++++++++++++++++++++++++++++++++
CodeGrade provides essential communication tools between graders in the shape of
e-mail notifications. These notifications rely on graders indicating that they
are done grading by setting their state to 'Done' after all grading is finished.

.. warning::

    It is possible to set a grader to the 'Done' state that did not finish
    grading all assigned submissions, a warning is shown in this case.

E-mail Notifications
++++++++++++++++++++++
CodeGrade provides two types of e-mail notifications to enable essential
communication between graders:

* **Graders** notification: send an e-mail at a specified date and time to all
  graders that have not yet finished grading.
* **Finished** notification: send an e-mail to a specified e-mail address to
  notify when all graders are finished grading.

.. note:: Notifications rely on the manually set status by the graders.

Linters
~~~~~~~~~
CodeGrade provides several linters (e.g. Pylint, Checkstyle). A linter analyses
submissions to flag programming errors, bugs, stylistic errors, or suspicious
constructs, depending on the linter's characteristics. After selecting a linter
and optionally writing a config file (custom configuration can be given, please
consult the specific linter's documentation for details on writing
configuration files), the linter can be run using the 'Run' button.

When the linter has run on all submissions, a list can be shown with the status
for each submission by clicking 'Show more information'. The submissions are
sorted such that ones that crashed the linter appear at the top of the list.
Logs of the runs that crashed can be downloaded individually per submission by
clicking the 'Download' button.

The output of the linter will be displayed in the :ref:`Codeviewer
<codeviewer-chapter>` and indicated by red line numbers that display the linter
output when hovering over. Linters can often be useful to provide a quick
overview of stylistic errors or bad constructs.

The version of the linters doesn't have to be the same for each CodeGrade
instance. However, official CodeGrade instances always try to run the latest
version.

Checkstyle
++++++++++
Checkstyle is a linter for Java code. It checks Java code primarily for
stylistic errors, like wrong indentation. It can be configured by a XML file,
you can find documentation on how to write such a configuration file
`here <http://checkstyle.sourceforge.net/config.html>`__.


.. note::

    Not all configuration fields are allowed because of security. For the same
    reason it is also not possible to upload your own checkers.

Flake8
++++++
Flake8 is a linter for Python code. It checks for code style. By default it
checks if code adheres to PEP8, but you can change some rules by uploading a
configuration file. The documentation for this file can be found
`here <http://flake8.pycqa.org/en/latest/user/configuration.html>`__.

Flake8 is run without any extensions by default. If such extensions are required
please :ref:`contact us <contact-chapter>`.

PMD
++++
PMD is a linter that supports multiple languages, of which support for the most
common one, Java, is implemented in CodeGrade. The linter focuses on coding
style and common functional errors, but can also find stylistic errors. The
linter has to be configured using rulesets, how to do this is described here
`here <https://pmd.github.io/pmd-6.10.0/pmd_userdocs_making_rulesets.html>`__.

.. note::

    Because of security reasons, it is not possible to create custom rules, nor
    is it possible to create XPath rules. This is because of security.

Pylint
++++++
Pylint is a linter for Python code. It checks Python *packages*, this means it
currently only works for submissions that contain a ``__init__.py`` file. If
Pylint failed to run because no package could be found it places a comment on
the first line of each python file.

Pylint is configured using a configuration file that you can upload. This
configuration file is passed directly to Pylint. Documentation about Pylint and
this configuration file can be viewed `here <https://docs.pylint.org>`__.

Plagiarism
~~~~~~~~~~~~~~~~~~~~~~
CodeGrade offers built in plagiarism detection functionalities, to efficiently
and clearly detect for plagiarism on programming assignments. In this tab you
can configure plagiarism runs. Please consult the :ref:`Plagiarism Detection
<plagiarism-chapter>` chapter for more information.

Rubric
~~~~~~~~~~
Rubrics are an indispensable tool in modern day education and allow for easy and
consistent grading between different graders and submissions. In this tab you
can setup and edit the rubric of the assignment. Sophisticated rubrics can be
made in CodeGrade. A basic rubric consist of multiple categories that all have
multiple levels and corresponding points. All components in a CodeGrade rubric
can have a name and description.

A new category can be created by clicking the :fa:`plus` button. A name and
description can be given, furthermore a number of levels can be given. New
levels are automatically added by typing in previous levels and levels can be
removed by pressing the :fa:`times` button.

Each level can be assigned a number of points (usually descending). The total number of points is automatically incremented by the given
points but can be manually overridden if requested.

.. note:: A rubric is only saved after pressing the 'Submit' button, it is recommended to occasionally save the rubric to prevent losing work.


Creating a new Assignment
~~~~~~~~~~~~~~~~~~~~~~~~~
With the right :ref:`permissions <permissions-chapter>` new assignments for a
course can be created. To do this, select the course in the Course menu and
click on it to display its assignment list. A new assignment can now be created
for this course using the :fa:`plus` button on the bottom of the
menu-screen. Press *Add* after specifying a name for the assignment to create
it.
