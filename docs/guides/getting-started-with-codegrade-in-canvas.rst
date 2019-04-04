Getting started with CodeGrade in Canvas
--------------------------------------------

.. include:: getting-started-introduction.rst

Integration with Canvas
=========================

All functionalities are bundled in one complete environment for programming
education, that integrates with Canvas. We use the LTI protocol to securely
communicate and synchronize CodeGrade with Canvas. Most likely, CodeGrade has
already been correctly integrated with Canvas by your system administrator,
please contact us if not.

CodeGrade accounts are automatically created and linked to current Canvas
accounts. CodeGrade can be accessed both from **within Canvas**, showing a more
narrow version of CodeGrade in a container on Canvas, or from the CodeGrade
**standalone website**: *<your-institution>.codegra.de*. There is no difference
between these two, and opening the standalone website via Canvas using the
**“New tab”** button allows you to be automatically logged in.

CodeGrade accounts that are automatically created and linked from within Canvas
will not have a password, and are only accessible by the shared session with Canvas.

.. include:: setup-password.rst

Canvas synchronisation
~~~~~~~~~~~~~~~~~~~~~~~

The following data is shared between CodeGrade and Canvas:

- Usernames

- Full names

- Email addresses

- Course names

- Assignment names

- Assignment deadlines

- Assignment state

- Grades (only passed back from CodeGrade to Canvas)

.. include:: creating-a-canvas-assignment.rst

Setting up your course
========================

After creating your first CodeGrade assignment from within Canvas, a course
will be automatically created in CodeGrade. To **manage** the course options
**press “Courses”** (:fa:`book`), select your course and press the :fa:`cog`
**icon**. Below is a brief overview of the tabs in course management.

Members
~~~~~~~~

After a user (student, TA or teacher) opens a CodeGrade assignment in Canvas
for the first time in your course, they will automatically be added as a member
of the course, CodeGrade will use the **role** this user has in Canvas. On this tab,
you can **change the role** of a member if it’s not correct, for example, from
**Student** to **TA**.

.. warning::
    CodeGrade will automatically use the role the user has in Canvas. In general,
    it is not necessary to change roles, only do this if necessary.

Permissions
~~~~~~~~~~~~

On this page, you can change the permissions of the roles in the course. For
example, you could give your TAs more permissions. Every permission is explained
by the :fa:`info` icon.

.. warning::
    The default permissions will probably suit your course.

Groups
~~~~~~~~~

If you want to use groups, you can create group sets here. A group set can be
used by multiple assignments in the same course. **CodeGrade does not synchronize
groups with Canvas**, so make sure your assignments in Canvas are individual
assignments (no group submission) and manage your groups in CodeGrade.
**CodeGrade will automatically send back all grades and feedback to all individual
group members to Canvas correctly.** Depending on permissions you can allow
students to join a group themselves or only allow Teachers or TAs to add students
to a group. If you want to **change** these permissions, you can do so on the
**permissions** page explained above.
:ref:`Click here to learn more about setting up your groups <set-up-group-assignment>`.

Setting up your assignment
=============================

By clicking the :fa:`cog` icon on an assignment you enter the **assignment management page**.
This page allows you to set up **groups**, run **linters**, start **plagiarism runs**,
and add or edit the **rubric**.

General
~~~~~~~~~

On the **“General”** page you can edit several general options. You can also select
a group set to use, if you decide to make an assignment a group assignment.
Furthermore you can set bonus points.

.. warning::
    The deadline, name and visibility of the assignment is configured within Canvas.

Graders
~~~~~~~~~

To divide submissions between your teachers and/or TAs, graders can be assigned
to individual submissions. This can be done either *manually*, using the dropdown
menus on the submission list page, or *randomly* using the **“Divide Submissions”**
tool on the “Graders” page on the assignment management page.

Submission divisions can be *shared* between different assignments of the same
course. Connect the submission division with another assignment to use the
previously created division.
:ref:`Click here to learn more about dividing submissions <dividing-submissions>`

.. note::
    Connecting divisions can be very helpful if you want the same TAs
    to grade the same students for each assignment.

Linters
~~~~~~~~

On the **“Linters”** page you can run a linter on all submissions. A linter checks
code style. After a run, all errors found by the linter are **automatically
shown** in the Code Viewer on the corresponding line.

.. note::
    If you want to use a linter that is not yet integrated in CodeGrade,
    let us know at `support@codegrade.com <mailto:support@codegrade.com>`_, and we’ll make sure to add it to
    CodeGrade in our next release.

Plagiarism
~~~~~~~~~~~

On the **"Plagiarism"** page it is possible to start plagiarism runs to detect fraud.
:ref:`Click here to find out more about starting plagiarism runs <checking-for-plagiarism>`

Rubric
~~~~~~~~~

Rubrics are a scoring guide used by graders, they make grading more **consistent**
and **efficient** for teachers, and help students **understand** their grade. Rubrics
can be created within CodeGrade and consist of multiple categories. Each
category has multiple levels, with a corresponding amount of points.
Examples of categories are *functionality*, *code style*, *documentation*,
*code structure* and *version control*. Examples of levels are *unacceptable (0)*,
*needs improvement (1)*, *good (2)* and *excellent (3)*. CodeGrade will **automatically
calculate** the grade after filling in the rubric, by taking the sum of the
points and dividing this by the maximum amount of points.
This grade can be overridden. :ref:`Click here to learn more about setting up rubrics <set-up-rubric>`

.. note::
    Rubrics can also be imported from previous assignments.

The Code Viewer
==================

The heart of CodeGrade is the Code Viewer. This enables you to grade and review
submissions from within our website and allows students to intuitively see
their feedback displayed in their code.

*Submissions* handed in as archives are *automatically* extracted and displayed
in the file-tree next to the *Code Viewer*. Of course, multiple individual files
can also be uploaded in CodeGrade. The Code Viewer supports over **175
programming languages**, **Jupyter Notebooks**, **PDF-files** and **images**.

Inline feedback
~~~~~~~~~~~~~~~~

The most intuitive way to give feedback on programming assignments is to be
able to write comments on **specific lines or blocks of code**. This is made
possible by the **inline feedback** in the Code Viewer.

Press on any line and start
typing your feedback, click the :fa:`check` button to save the feedback or press the
:fa:`cross` button to delete.

.. note::
    Pro tip: press :kbd:`Ctrl+Enter` to save feedback efficiently.

Snippets
~~~~~~~~~

Experience tells us that the same lines of feedback are oftentimes given
multiple times to multiple students. We introduced **snippets** to make grading
with inline feedback **more efficient**. Click the :fa:`plus` icon when entering line
feedback to save the comment as a snippet. This snippet can now be re-used
in the future by **typing its short name** and pressing :kbd:`Tab` to autocomplete.

Full management of snippets can be done in the **“Profile Page"** (:fa:`user-circle-o`),
snippets are personal and can be used over multiple assignments and courses.

.. note::

    Course wide snippets are available in CodeGrade too, these can be set up by
    the teacher of the course on the **Course Management page** and can be used
    by all graders of the course.

Rubrics
~~~~~~~~

If an assignment has a rubric (:ref:`click here to learn more about setting up rubrics <set-up-rubric>`),
the rubric **can be used and filled in** from within the Code Viewer.
Press the :fa:`th` button to display the rubric and select the levels for the
submission to generate a grade using the rubric.

.. warning::
    **Do not forget to save the filled in rubric after grading!** Rubric grades
    can be manually overwritten.

General feedback
~~~~~~~~~~~~~~~~~~~

In addition to the new ways of giving feedback in CodeGrade, conventional
general feedback can be given too. Press the :fa:`pencil-square-o` button to
give and save general feedback.

Overview mode
~~~~~~~~~~~~~~~~

The overview mode can be accessed by clicking :fa:`binoculars` or is automatically shown after
an assignment’s state is set to **“Done”** (:fa:`check`). The overview mode provides an
overview of all line feedback, the general feedback and the teacher
revision (see “Filesystem” for more information on the teacher revision).
This is especially useful for students.

Code Viewer settings
~~~~~~~~~~~~~~~~~~~~~

Like your favourite editor, the Code Viewer provides numerous settings to **fit your preferences**.
Click :fa:`cog` to change:

- Whitespace visibility

- Syntax highlighting

- Code font size

- Dark/light theme

- Code context size

Student Experience
=====================

Students hand in an assignment on **Canvas** via the CodeGrade container after
opening the assignment. After handing in, students can browse through their
code to check if it is correctly handed in. Before handing in they can
click on the **“rubric”** (:fa:`th`) button to show the rubric for this assignment.
This means students **know what is expected** of them.

After an assignment is set to **“Done”** (:fa:`check`) grades are automatically sent
back to Canvas. Students can then view their feedback inside the
CodeGrade container in Canvas after clicking on their grade or
navigating to the assignment.

.. note::
    If an assignment is in the **“Done”** (:fa:`check`)
    state, all new grades or edits are passed back to Canvas immediately.

By default students will see their feedback in the **“Overview”** (:fa:`binoculars`) mode,
so they immediately see all feedback given to them. If a **rubric** is used,
this can also be seen in the overview mode. A student can switch to
normal mode to browse through their code normally.

.. note::
    We recommend graders to make use of the standalone CodeGrade website, but the
    CodeGrade container within Canvas is sufficient for students. It is not
    possible for students to hand in assignments in the standalone environment.

Contact us and support
========================
If you have any questions, don’t hesitate to contact us. You can email us at
`support@codegrade.com <mailto:support@codegrade.com>`_. In addition to questions and bug reports,
we always love to get feedback and suggestions on how we can improve
CodeGrade to better fit your education.
