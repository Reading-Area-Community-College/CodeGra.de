Changelog
==========

Version 1.6.6 (Izanami.2)
-------------------------

**Released**: April 04th, 2019

You can now set up detailed hand-in requirements for your students,
create course snippets and the submission page is easier to and has more
information (including the possibility to upload multiple files).

**Features & Updates**

-  Add a new version of the ignore file
   `(#889) <https://github.com/CodeGra-de/CodeGra.de/pull/889>`__: this
   makes it possible to set detail hand-in requirements for students.
-  Allow uploading multiple files
   `(#888) <https://github.com/CodeGra-de/CodeGra.de/pull/888>`__:
   students can now upload multiple files and archives.
-  Add course snippets
   `(#897) <https://github.com/CodeGra-de/CodeGra.de/pull/897>`__:
   course snippets are shared between all teachers and ta's of a course.
-  Add Moodle support
   `(#873) <https://github.com/CodeGra-de/CodeGra.de/pull/873>`__: full
   LTI integration with Moodle.
-  Add Blackboard support
   `(#820) <https://github.com/CodeGra-de/CodeGra.de/pull/820>`__: full
   LTI integration with Blackboard.
-  Enhance documentation
   `(#875) <https://github.com/CodeGra-de/CodeGra.de/pull/875>`__:
   better documentation which includes user guides.
-  Rewrite submission list page header
   `(#885) <https://github.com/CodeGra-de/CodeGra.de/pull/885>`__: more
   information, including a better visible rubric for students.

**Minor updates**

-  Edit snippets in modal
   `(#855) <https://github.com/CodeGra-de/CodeGra.de/pull/855>`__: a
   better UI for adding snippets.
-  Add border when CodeGrade is loaded in an iframe in Canvas
   `(#883) <https://github.com/CodeGra-de/CodeGra.de/pull/883>`__: this
   makes it more clear where CodeGrade begins and Canvas ends.
-  White background for sidebar when not in dark theme
   `(#865) <https://github.com/CodeGra-de/CodeGra.de/pull/865>`__: this
   makes the light mode more beautiful.
-  Improve the way rubric maximum points are presented
   `(#895) <https://github.com/CodeGra-de/CodeGra.de/pull/895>`__: added
   warnings and improved the UI, so the feature is not misused.
-  Make it possible to filter submissions by member of the group
   `(#840) <https://github.com/CodeGra-de/CodeGra.de/pull/840>`__.
-  Increase the default value used for minimal similarity for jplag
   `(#894) <https://github.com/CodeGra-de/CodeGra.de/pull/894>`__:
   changed it from 25 to 50, making sure users don't get too much cases
   by default.
-  Add multiple file uploader to documentation
   `(#896) <https://github.com/CodeGra-de/CodeGra.de/pull/896>`__.
-  Update documentation to apply to new snippet management UI
   `(#891) <https://github.com/CodeGra-de/CodeGra.de/pull/891>`__.
-  Improve filtering the course users
   `(#893) <https://github.com/CodeGra-de/CodeGra.de/pull/893>`__:
   increased the efficiency of the filtering.

**Fixes**

-  Make sure duplicate filenames are detected and renamed
   `(#898) <https://github.com/CodeGra-de/CodeGra.de/pull/898>`__.
-  Show when user has no snippets
   `(#890) <https://github.com/CodeGra-de/CodeGra.de/pull/890>`__.
-  Set default deadline time to 23:59
   `(#879) <https://github.com/CodeGra-de/CodeGra.de/pull/879>`__.
-  Fix new tab button position in sidebar
   `(#867) <https://github.com/CodeGra-de/CodeGra.de/pull/867>`__.
-  Fix home page logo position
   `(#851) <https://github.com/CodeGra-de/CodeGra.de/pull/851>`__.
-  Fix header text color in dark theme
   `(#852) <https://github.com/CodeGra-de/CodeGra.de/pull/852>`__.
-  Fix file tree resizer z-index
   `(#853) <https://github.com/CodeGra-de/CodeGra.de/pull/853>`__.
-  Rename "Old password" to "Current password"
   `(#856) <https://github.com/CodeGra-de/CodeGra.de/pull/856>`__.

Version 1.3.29 (Izanami.1)
--------------------------

**Released**: March 09th, 2019

Along with many UI improvements and bug fixes, you can connect grading divisions
between assignments and import rubrics from previous assignments.

**Features & Updates**

- Make it possible to connect assignment divisions  `(#794)
  <https://github.com/CodeGra-de/CodeGra.de/pull/794>`__: This makes it possible
  to have the same TAs grade the same students over the duration of the entire
  course.
- Make it possible to import rubrics from other assignments `(#788)
  <https://github.com/CodeGra-de/CodeGra.de/pull/788>`__.
- Improve UI/UX for running linters `(#814)
  <https://github.com/CodeGra-de/CodeGra.de/pull/814>`__: Logs of the linter
  runs on the individual submissions can now be viewed.
- Enable use of multiple LTI providers `(#811)
  <https://github.com/CodeGra-de/CodeGra.de/pull/811>`__: Soon we will be able
  to connect with Blackboard, Moodle, Brightspace, and others!
- Make it possible to resize the filetree `(#804)
  <https://github.com/CodeGra-de/CodeGra.de/pull/804>`__
  `(#834) <https://github.com/CodeGra-de/CodeGra.de/pull/834>`__.

**Minor fixes**

- Make it impossible to list all users on the system by searching `(#798)
  <https://github.com/CodeGra-de/CodeGra.de/pull/798>`__: All users on the
  system could be listed by almost anyone.
- Confirm clearing a rubric `(#833)
  <https://github.com/CodeGra-de/CodeGra.de/pull/833>`__: Instead of requiring
  the user to click the submit button for the grade to reset a rubric, the new
  submit button confirmation popover is used to confirm the action.
- Rewrite SubmitButton component `(#790)
  <https://github.com/CodeGra-de/CodeGra.de/pull/790>`__
  `(#828) <https://github.com/CodeGra-de/CodeGra.de/pull/828>`__
  `(#806) <https://github.com/CodeGra-de/CodeGra.de/pull/806>`__: Buttons will
  not change size anymore, and when an error occurs the button will wait for
  the user to close the message, instead of the error message disappearing
  after a few seconds, not giving the user a chance to read the entire thing.
- Change sidebar login icon `(#830)
  <https://github.com/CodeGra-de/CodeGra.de/pull/830>`__: The icon was ugly and
  its meaning not very obvious.
- Add button to open in new tab in LTI `(#826)
  <https://github.com/CodeGra-de/CodeGra.de/pull/826>`__: It was unclear that
  the logo in the sidebar would open CodeGrade in a new tab, so an extra button
  has been added.
- Remove show password button `(#825)
  <https://github.com/CodeGra-de/CodeGra.de/pull/825>`__: The button on the
  right side of the password inputs has been removed, as it is not very useful.
- Show progress for plagiarism runs `(#813)
  <https://github.com/CodeGra-de/CodeGra.de/pull/813>`__: Plagiarism runs could
  take quite some time but didn't show the progress until they quit
  successfully or crashed.
- Make it possible to search the homegrid `(#812)
  <https://github.com/CodeGra-de/CodeGra.de/pull/812>`__.
- Make it possible to download the plagiarism log `(#802)
  <https://github.com/CodeGra-de/CodeGra.de/pull/802>`__.
- Add warning on permission management page `(#801)
  <https://github.com/CodeGra-de/CodeGra.de/pull/801>`__: When permissions are
  changed it shows a notification that the page must be reloaded for the
  changes to take effect.
- Add a release notifier on the home grid `(#787)
  <https://github.com/CodeGra-de/CodeGra.de/pull/787>`__: Whenever a new version
  of CodeGrade is installed, a notification will be shown on the home page with
  a link to this changelog.

**Fixes**

- Add formatted_deadline property to the course store for assignments `(#835)
  <https://github.com/CodeGra-de/CodeGra.de/pull/835>`__.
- Make sure permissions are removed on logout `(#832)
  <https://github.com/CodeGra-de/CodeGra.de/pull/832>`__.
- Add smaller logo on standalone pages `(#831)
  <https://github.com/CodeGra-de/CodeGra.de/pull/831>`__.
- Make sure only plagiarism runs which have finished can be viewed `(#827)
  <https://github.com/CodeGra-de/CodeGra.de/pull/827>`__.
- Make sure password reset works and logs in user `(#829)
  <https://github.com/CodeGra-de/CodeGra.de/pull/829>`__.
- Make sure error message is correct when empty archive is uploaded `(#819)
  <https://github.com/CodeGra-de/CodeGra.de/pull/819>`__.
- Make sure we don't mutate store objects in the rubric editor `(#818)
  <https://github.com/CodeGra-de/CodeGra.de/pull/818>`__.
- Make sure order of submissions is stable `(#816)
  <https://github.com/CodeGra-de/CodeGra.de/pull/816>`__.
- Fix large amount of trailing zeros in the rubric viewer `(#817)
  <https://github.com/CodeGra-de/CodeGra.de/pull/817>`__.
- Prevent error in console when not logged in on page load `(#809)
  <https://github.com/CodeGra-de/CodeGra.de/pull/809>`__.
- Make sure 500 never occur because of ``__maybe_add_warning`` function `(#807)
  <https://github.com/CodeGra-de/CodeGra.de/pull/807>`__.
- Merge the loaders of the plagiarism runner `(#805)
  <https://github.com/CodeGra-de/CodeGra.de/pull/805>`__.
- Fix bug when reloading assignments on submission page `(#799)
  <https://github.com/CodeGra-de/CodeGra.de/pull/799>`__.
- Add link to about us page in the footer `(#800)
  <https://github.com/CodeGra-de/CodeGra.de/pull/800>`__.
- Clearer plagiarism similarity placeholder `(#792)
  <https://github.com/CodeGra-de/CodeGra.de/pull/792>`__.
- Reserve some extra special filenames `(#793)
  <https://github.com/CodeGra-de/CodeGra.de/pull/793>`__.

Version 1.2.19 (Izanami)
------------------------

**Released**: Februari 07th, 2019

**Features & Updates**

- Group assignments `(#715)
  <https://github.com/CodeGra-de/CodeGra.de/pull/715>`__: With this release
  we have added group assignments. It is possible to create groups, share
  them between assignments, and submit as a group. Groups can be given
  a nice name, that is easily remembered by the TA.
- Add support for 7zip as archive format `(#738)
  <https://github.com/CodeGra-de/CodeGra.de/pull/738>`__
- Make late submissions stand out `(#739)
  <https://github.com/CodeGra-de/CodeGra.de/pull/739>`__: Submissions that have
  been handed in after the deadline are highlighted in the submissions list.
- Make it possible to display IPython notebooks `(#742)
  <https://github.com/CodeGra-de/CodeGra.de/pull/742>`__: CodeGrade now renders
  handed in IPython notebooks in the web interface instead of showing a JSON
  blob. Additionally, markdown files are also rendered. Teachers can place
  comments in both types of files, as well as on image files now. This also
  adds a message when a file does not end in a newline character.

**Minor updates**

- Show message when uploaded file is empty `(#766)
  <https://github.com/CodeGra-de/CodeGra.de/pull/766>`__: When a file is empty,
  it wouldn't show up at all in the code viewer. This changes it to show
  a message, indicating that the file is empty.
- Make the user selector more clear `(#752)
  <https://github.com/CodeGra-de/CodeGra.de/pull/752>`__: The user selector now
  shows a magnifying glass, indicating that the user can type to search for
  users.
- Use flatpickr datetime picker instead of native `(#737)
  <https://github.com/CodeGra-de/CodeGra.de/pull/737>`__: Date/time inputs have
  been changed to use a date picker, so users of browsers besides Chromium can
  now also pleasantly select a date or time.
- Change icon for user in the sidebar `(#747)
  <https://github.com/CodeGra-de/CodeGra.de/pull/747>`__

**Fixes**

- Hide plagiarism providers when there is only one `(#745)
  <https://github.com/CodeGra-de/CodeGra.de/pull/745>`__
- Make sure it is possible to ignore single files `(#767)
  <https://github.com/CodeGra-de/CodeGra.de/pull/767>`__: When a student
  submitted a single file instead of an archive, the student would not be warned
  that the file was ignored by the assignment's CGignore file.
- Make sure confirmations work correctly when submitFunction is used `(#748)
  <https://github.com/CodeGra-de/CodeGra.de/pull/748>`__
- Improve grade viewer `(#764)
  <https://github.com/CodeGra-de/CodeGra.de/pull/764>`__: It was not possible to
  simultaneously submit a change to a rubric and override the grade calculated
  by the rubric.
- Various front-end UI fixes `(#763)
  <https://github.com/CodeGra-de/CodeGra.de/pull/763>`__
- Various browser specific UI fixes `(#768)
  <https://github.com/CodeGra-de/CodeGra.de/pull/768>`__

Version 1.1.4 (HereBeMonsters.3)
---------------------------------

**Released**: January 16th, 2019

**Features & Updates:**

- Add PMD and Checkstyle linters `(#734)
  <https://github.com/CodeGra-de/CodeGra.de/pull/683>`__: Addition of two Java
  linters: PMD and Checkstyle. For security reasons, some restrictions on config
  apply. Please see the documentation for more details

-  Add snippet completion and selection
   `(#655) <https://github.com/CodeGra-de/CodeGra.de/pull/655>`__: This
   makes it easier for users to use and add snippets.

**Fixes:**

-  Fix a bug hiding indentation on lines with linter errors
   `(#710) <https://github.com/CodeGra-de/CodeGra.de/pull/710>`__: When
   linting lines with errors didn’t show indentation.
-  Fix dark special holiday logo.
   `(#711) <https://github.com/CodeGra-de/CodeGra.de/pull/711>`__
-  Make it impossible to upload too large archives
   `(#709) <https://github.com/CodeGra-de/CodeGra.de/pull/709>`__: This
   makes it way harder for users to bypass our restrictions to upload
   very large archives.
-  Various internal fixes and improvements.
   `(#716) <https://github.com/CodeGra-de/CodeGra.de/pull/716>`__
-  Don’t apply “mine” filter when assigning first submission to self
   `(#717) <https://github.com/CodeGra-de/CodeGra.de/pull/717>`__: When
   no submission had an assignee and you assigned yourself it filtered
   all other submissions directly.
-  Make sure the grade is updated when rubric is.
   `(#731) <https://github.com/CodeGra-de/CodeGra.de/pull/731>`__
-  Improve worst case performance in some plagiarism cases.
   `(#732) <https://github.com/CodeGra-de/CodeGra.de/pull/732>`__

Version 1.0.22 (HereBeMonsters.2)
----------------------------------

**Released**: November 21st, 2018

**Features & Updates:**

-  Enforce minimal password strength
   `(#683) <https://github.com/CodeGra-de/CodeGra.de/pull/683>`__
   `(#697) <https://github.com/CodeGra-de/CodeGra.de/pull/697>`__:
   CodeGrade now enforces a minimum password strength for all users. A
   warning is also shown if a user logs in with a password that doesn't
   adhere to the current requirements. We recommend all users to update
   their passwords if they receive such a warning.
-  Update course and assignment name on LTI launch
   `(#682) <https://github.com/CodeGra-de/CodeGra.de/pull/682>`__: If
   the name of a course or assignment changes within your LMS this
   change is now copied in CodeGrade.
-  Do lti launch on grade result
   `(#681) <https://github.com/CodeGra-de/CodeGra.de/pull/681>`__: When
   viewing new grades this will trigger an LTI launch. This means you
   will always be logged-in in CodeGrade with the current LMS user.
-  Show a loader instead of the delete button for plagiarism checks that
   are still running.
   `(#700) <https://github.com/CodeGra-de/CodeGra.de/pull/700>`__

**Fixes:**

-  Only show register button when the feature is enabled.
   `(#679) <https://github.com/CodeGra-de/CodeGra.de/pull/679>`__
-  Make it possible to create PDF manuals.
   `(#687) <https://github.com/CodeGra-de/CodeGra.de/pull/687>`__
-  Fix plagiarism detail viewer
   `(#690) <https://github.com/CodeGra-de/CodeGra.de/pull/690>`__:
   Because of a misplaced bracket it was not possible to view plagiarism
   cases.
-  Always do an initial grade passback
   `(#692) <https://github.com/CodeGra-de/CodeGra.de/pull/692>`__: This
   reverts a change in version 1.0.0 which caused Canvas to not remove
   CodeGrade assignments from the todo list of students. By doing a LTI
   passback when students hand-in a submission the assignment should be
   removed from their todo list.
-  Various small logging fixes.
   `(#693) <https://github.com/CodeGra-de/CodeGra.de/pull/693>`__
-  Redact emails of other users
   `(#695) <https://github.com/CodeGra-de/CodeGra.de/pull/695>`__: This
   is a minor **breaking change**. When serializing a user an ``email``
   key was always sent including the email of every user. With this
   change the ``email`` key is only sent with the extended serialization
   of a user, and the value is changed to ``'<REDACTED>'`` for every
   user except the currently logged-in user. This prevents people in the
   same course from seeing each others email.
-  Improve speed of plagiarism route
   `(#694) <https://github.com/CodeGra-de/CodeGra.de/pull/694>`__: By
   using the database in a more efficient way this route should become
   about twice as fast!
-  Various styling fixes.
   `(#701) <https://github.com/CodeGra-de/CodeGra.de/pull/701>`__
   `(#703) <https://github.com/CodeGra-de/CodeGra.de/pull/703>`__

Version 1.0.7 (HereBeMonsters.1)
--------------------------------

**Released**: November 12th, 2018

**Features & Updates:**

- Support files encoded as ISO-8859-1 (latin1) in the frontend.
  `(#666) <https://github.com/CodeGra-de/CodeGra.de/pull/666>`_

**Fixes:**

- Make it impossible to override the special files of the CodeGrade
  filesystem. `(#673) <https://github.com/CodeGra-de/CodeGra.de/pull/673>`_
- Various frontend fixes. `(#664) <https://github.com/CodeGra-de/CodeGra.de/pull/664>`_ `(#669) <https://github.com/CodeGra-de/CodeGra.de/pull/669>`_ `(#671) <https://github.com/CodeGra-de/CodeGra.de/pull/671>`_ `(#674) <https://github.com/CodeGra-de/CodeGra.de/pull/674>`_
- Improve documentation. `(#672) <https://github.com/CodeGra-de/CodeGra.de/pull/672>`_

Version 1.0.0 (HereBeMonsters)
------------------------------

**Released**: October 30th, 2018

**Features & Updates:**

-  Add Plagiarism checkers `(#486) <https://github.com/CodeGra-de/CodeGra.de/pull/486>`_ `(#513) <https://github.com/CodeGra-de/CodeGra.de/pull/513>`_ `(#536) <https://github.com/CodeGra-de/CodeGra.de/pull/536>`_ `(#555) <https://github.com/CodeGra-de/CodeGra.de/pull/555>`_ `(#508) <https://github.com/CodeGra-de/CodeGra.de/pull/508>`_ `(#556) <https://github.com/CodeGra-de/CodeGra.de/pull/556>`_
   `(#645) <https://github.com/CodeGra-de/CodeGra.de/pull/645>`_ `(#576) <https://github.com/CodeGra-de/CodeGra.de/pull/576>`_: It is now possible to check for plagiarism in
   CodeGrade. This enables privacy aware plagiarism checking. It is
   possible to use check against old CodeGrade assignment and upload
   base code and old submissions that are not in CodeGrade. For more
   information see our documentation.

-  Make it possible give grades higher than ten `(#500) <https://github.com/CodeGra-de/CodeGra.de/pull/500>`_: Teachers can now
   indicate that students can receive a grader higher than 10 for an
   assignment, making it possible to create assignments with bonus
   points in CodeGrade. When using within LTI this requires a new LTI
   parameter.

   You should add the following to the ``<blti:custom>`` section of your
   canvas LTI config for CodeGrade:

   .. code:: xml

      <lticm:property name="custom_canvas_points_possible">
        $Canvas.assignment.pointsPossible
      </lticm:property>

**Minor changes:**

-  Change homepage to login screen `(#480) <https://github.com/CodeGra-de/CodeGra.de/pull/480>`_ `(#496) <https://github.com/CodeGra-de/CodeGra.de/pull/496>`_ `(#501) <https://github.com/CodeGra-de/CodeGra.de/pull/501>`_ `(#557) <https://github.com/CodeGra-de/CodeGra.de/pull/557>`_ `(#616) <https://github.com/CodeGra-de/CodeGra.de/pull/616>`_:
   The homepage has been improved to show all your courses and
   assignments at a glance when logged in.
-  Use new logos `(#481) <https://github.com/CodeGra-de/CodeGra.de/pull/481>`_ `(#506) <https://github.com/CodeGra-de/CodeGra.de/pull/506>`_: This updates our logo to the newest and
   greatest version!
-  Allow .tar.xz archives to be uploaded `(#492) <https://github.com/CodeGra-de/CodeGra.de/pull/492>`_: This further improves
   the flexibility CodeGrade gives students when handing in submissions.
-  Fix infinite loop overview mode `(#477) <https://github.com/CodeGra-de/CodeGra.de/pull/477>`_: In some combinations of
   permissions loading the overview mode resulted in an infinite loader.
-  Add general feedback tab to overview mode `(#523) <https://github.com/CodeGra-de/CodeGra.de/pull/523>`_: This further
   decreases the chance that students will miss any of their feedback.
-  Improve speed of diffing by using another library `(#529) <https://github.com/CodeGra-de/CodeGra.de/pull/529>`_: Viewing the
   diff between two large files is a lot faster!
-  Remove the option to automatically generate keys `(#554) <https://github.com/CodeGra-de/CodeGra.de/pull/554>`_: It is no
   longer possible to generate the ``secret_key`` or ``lti_secret_key``
   configuration options. Please update your config accordingly.
-  Rewrite snippets manager `(#551) <https://github.com/CodeGra-de/CodeGra.de/pull/551>`_: This rewrite should make creating,
   using, deleting and updating snippets faster and more reliable.
-  Drastically improve the experience of CodeGrade on mobile `(#558) <https://github.com/CodeGra-de/CodeGra.de/pull/558>`_: It
   is now way easier to use CodeGrade on mobile.
-  Filter users in the user selector `(#553) <https://github.com/CodeGra-de/CodeGra.de/pull/553>`_: When selecting users (when
   uploading for others, or adding to courses) only show users will be
   shown that can be selected.
-  Improve handling of LTI `(#561) <https://github.com/CodeGra-de/CodeGra.de/pull/561>`_ `(#588) <https://github.com/CodeGra-de/CodeGra.de/pull/588>`_: A complete rewrite of LTI
   backend handling. This should improve the stability of passbacks by a
   lot. This also guarantees that the submission date in Canvas and
   CodeGrade will match exactly. This also adds a new convenience route
   ``/api/v1/lti/?lms=Canvas`` to get lti config for the given LMS
   (Canvas only supported at the moment).
-  Add items to the sidebar conditionally `(#578) <https://github.com/CodeGra-de/CodeGra.de/pull/578>`_ `(#580) <https://github.com/CodeGra-de/CodeGra.de/pull/580>`_ `(#600) <https://github.com/CodeGra-de/CodeGra.de/pull/600>`_: Depending
   on what page you are you will get extra items in the sidebar to help
   quick navigation. Currently plagiarism cases and submissions are
   added depending on the page.
-  Start caching submissions `(#643) <https://github.com/CodeGra-de/CodeGra.de/pull/643>`_ `(#636) <https://github.com/CodeGra-de/CodeGra.de/pull/636>`_: Submissions are cached in the
   front-end so changing between the codeviewer and submissions list is
   now way quicker.
-  Ensure all rubric rows have a maximum amount of >= 0 points `(#579) <https://github.com/CodeGra-de/CodeGra.de/pull/579>`_: It
   is no longer allowed to have rows in a rubric where the maximum
   possible score is < 0. If you needed this to create rubrics with
   bonus categories simply use the ‘Max points’ option in the rubric
   editor. All existing rubrics are not changed.

**Fixes:**

-  Various small bugs in the sidebar
-  Add a minimum duration on the permission manager loaders `(#521) <https://github.com/CodeGra-de/CodeGra.de/pull/521>`_: This
   makes it clearer that permissions are actually updated.
-  Throw an API error when a rubric row contains an empty header `(#535) <https://github.com/CodeGra-de/CodeGra.de/pull/535>`_:
   This is a backwards incompatible API change, however it doesn’t
   change anything for the frontend.
-  Fix broken matchFiles function `(#528) <https://github.com/CodeGra-de/CodeGra.de/pull/528>`_ `(#550) <https://github.com/CodeGra-de/CodeGra.de/pull/550>`_: This fixes a bug that
   files changed inside a directory would not show up in the overview
   mode.
-  Fix horizontal overflow on codeviewer `(#518) <https://github.com/CodeGra-de/CodeGra.de/pull/518>`_: The codeviewer would
   sometimes overflow creating a vertical scrollbar when displaying
   files containing a large amount of consecutive tabs.
-  Check if an assignment is loaded before getting its course `(#549) <https://github.com/CodeGra-de/CodeGra.de/pull/549>`_: In
   some rare cases LTI launches would fail be cause assignments were not
   loaded correctly.
-  Add structured logging setup `(#546) <https://github.com/CodeGra-de/CodeGra.de/pull/546>`_: This makes it easier to follow
   requests and debug issues.
-  Fix general feedback line wrapping `(#570) <https://github.com/CodeGra-de/CodeGra.de/pull/570>`_: Giving long lines as
   general feedback should be displayed correctly to the user now.
-  Add manage assignment button to submission list `(#574) <https://github.com/CodeGra-de/CodeGra.de/pull/574>`_: It is now
   possible to easily navigate to the manage assignment page from the
   submissions list.
-  Start using enum to store permissions in the backend `(#571) <https://github.com/CodeGra-de/CodeGra.de/pull/571>`_: Most
   routes will be faster by this design change.
-  Improve filetree design `(#599) <https://github.com/CodeGra-de/CodeGra.de/pull/599>`_ `(#611) <https://github.com/CodeGra-de/CodeGra.de/pull/611>`_ `(#587) <https://github.com/CodeGra-de/CodeGra.de/pull/587>`_: It is now easier to spot
   additions, changes and deletion directly in the filetree.
-  Add ``<noscript>`` tag `(#613) <https://github.com/CodeGra-de/CodeGra.de/pull/613>`_: An error message will be displayed when
   javascript is disabled.
-  Improve speed of filetree operations `(#623) <https://github.com/CodeGra-de/CodeGra.de/pull/623>`_: Loading large filetrees
   is now way quicker by using smarter data-structures.
-  Add health route `(#593) <https://github.com/CodeGra-de/CodeGra.de/pull/593>`_: It is now possible to more easily monitor the
   health of your CodeGrade instance.
-  Fix fontSize & contextAmount on submission page `(#633) <https://github.com/CodeGra-de/CodeGra.de/pull/633>`_: Sometimes the
   fields would show up empty, this shouldn’t happen anymore!
-  Replace submitted symlinks with actual files `(#627) <https://github.com/CodeGra-de/CodeGra.de/pull/627>`_: When a student
   uploads an archive with symlinks the student is warned and all
   symlinks are replaced by files explaining that the original files
   were symlinks but that those are not supported by CodeGrade.
-  Fix grade history popover boundary `(#625) <https://github.com/CodeGra-de/CodeGra.de/pull/625>`_: The grade history would
   sometimes show up outside the screen, but no more!
-  Make it impossible to submit empty archives `(#622) <https://github.com/CodeGra-de/CodeGra.de/pull/622>`_: A error is shown
   when a student tries to submit an archive without files.
-  Show toast when local-storage doesn’t work `(#607) <https://github.com/CodeGra-de/CodeGra.de/pull/607>`_: When a user has no
   local-storage available a warning is shown so the user knows that
   their experience might be sub-optimal.
-  Show author of general feedback and line comments `(#564) <https://github.com/CodeGra-de/CodeGra.de/pull/564>`_ `(#605) <https://github.com/CodeGra-de/CodeGra.de/pull/605>`_: The
   author of all general feedback and line comments is displayed to the
   user. Only users with the ``can_see_assignee`` permission will see
   authors.
-  Justify description popover text `(#596) <https://github.com/CodeGra-de/CodeGra.de/pull/596>`_: The text in descriptions is
   now justified and their popups will only show when the ‘i’ is
   clicked.
-  Only submit rubric items or normal grade `(#589) <https://github.com/CodeGra-de/CodeGra.de/pull/589>`_: In some rare cases
   overriding rubrics would result in a race condition, resulting in
   wrong case.
-  Redesign the download popover on the submission page `(#595) <https://github.com/CodeGra-de/CodeGra.de/pull/595>`_: This new
   design looks way better, but you tell us!
-  Only show overview mode when you have permission to see feedback
   `(#563) <https://github.com/CodeGra-de/CodeGra.de/pull/563>`_: When you don’t have permission to see feedback the overview
   mode will never be shown.
-  Various other performance improvements `(#566) <https://github.com/CodeGra-de/CodeGra.de/pull/566>`_: We always strive for
   the best performance possible, and again in this release we increased
   the performance of CodeGrade!
-  Make sure codeviewer is full width on medium pages `(#591) <https://github.com/CodeGra-de/CodeGra.de/pull/591>`_: This makes
   it easier to review and display code on smaller screens.
-  Use custom font in toasted actions `(#614) <https://github.com/CodeGra-de/CodeGra.de/pull/614>`_: It is now always possible
   to close toasts, even when your font cannot display ‘✖’.

Version 0.23.21 (GodfriedMetDenBaard.2)
-----------------------------------------

**Released**: May 4th, 2018

**Fixes:**

* Make long rubric item headers show an ellipsis `(#457) <https://github.com/CodeGra-de/CodeGra.de/pull/457>`_
* Fix sidebar shadow with more than one submenu level `(#456) <https://github.com/CodeGra-de/CodeGra.de/pull/456>`_
* Make sure grade is updated when non incremental rubric is submitted `(#450) <https://github.com/CodeGra-de/CodeGra.de/pull/450>`_
* Only force overview mode when not in query parameters `(#455) <https://github.com/CodeGra-de/CodeGra.de/pull/455>`_
* Fix non-editable general feedback area `(#452) <https://github.com/CodeGra-de/CodeGra.de/pull/452>`_
* Make sure non top-level submenus are hidden `(#451) <https://github.com/CodeGra-de/CodeGra.de/pull/451>`_

Version 0.23.13 (GodfriedMetDenBaard.1)
-----------------------------------------

**Released**: April 24th, 2018

**Fixes:**

* Actually make sure permissions are not deleted in migration `(#431) <https://github.com/CodeGra-de/CodeGra.de/pull/431>`_
* Make sure data is reloaded when switching course `(#432) <https://github.com/CodeGra-de/CodeGra.de/pull/432>`_
* Store submissions filter on any keyup, not just enter `(#438) <https://github.com/CodeGra-de/CodeGra.de/pull/438>`_
* Fix points width in non-editable rubric editor `(#434) <https://github.com/CodeGra-de/CodeGra.de/pull/434>`_
* Fix width of rubric items after 4th one `(#435) <https://github.com/CodeGra-de/CodeGra.de/pull/435>`_
* Fix (some of) the mess that is the rubric viewer `(#440) <https://github.com/CodeGra-de/CodeGra.de/pull/440>`_
* Fix tab borders in the dark theme `(#439) <https://github.com/CodeGra-de/CodeGra.de/pull/439>`_
* Use placeholder for the "new category" field in the rubric editor `(#441) <https://github.com/CodeGra-de/CodeGra.de/pull/441>`_
* Make sure general comment is updated after switching submission `(#446) <https://github.com/CodeGra-de/CodeGra.de/pull/446>`_

Version 0.23.5 (GodfriedMetDenBaard)
--------------------------------------

**Released**: April 24th, 2018

**Features & Updates:**

* Update readme and add new sections to it `(#391) <https://github.com/CodeGra-de/CodeGra.de/pull/391>`_
* Add linters feature `(#387) <https://github.com/CodeGra-de/CodeGra.de/pull/387>`_
* Add fixed max points feature `(#395) <https://github.com/CodeGra-de/CodeGra.de/pull/395>`_
* Use pylint instead of pyflake for linting `(#402) <https://github.com/CodeGra-de/CodeGra.de/pull/402>`_
* Make `pytest` run with multiple threads locally `(#403) <https://github.com/CodeGra-de/CodeGra.de/pull/403>`_
* Revamp entire frontend design `(#404) <https://github.com/CodeGra-de/CodeGra.de/pull/404>`_
* Make sure docs are published at docs.codegra.de `(#416) <https://github.com/CodeGra-de/CodeGra.de/pull/416>`_

**Fixes:**

* Make sure upload dialog is visible after deadline `(#375) <https://github.com/CodeGra-de/CodeGra.de/pull/375>`_
* Fix assignment state component `(#377) <https://github.com/CodeGra-de/CodeGra.de/pull/377>`_
* Make sure no persisted storage is used if it is not available `(#374) <https://github.com/CodeGra-de/CodeGra.de/pull/374>`_
* Fix the submission navbar navigation `(#376) <https://github.com/CodeGra-de/CodeGra.de/pull/376>`_
* Rename `stupid` to `student` in test data `(#385) <https://github.com/CodeGra-de/CodeGra.de/pull/385>`_
* Reduce the default permissions for the `TA` role `(#386) <https://github.com/CodeGra-de/CodeGra.de/pull/386>`_
* Fix bug with changing language after changing file `(#389) <https://github.com/CodeGra-de/CodeGra.de/pull/389>`_
* Fix thread safety problems caused by global objects `(#394) <https://github.com/CodeGra-de/CodeGra.de/pull/394>`_
* Fix problems with ignoring directories `(#399) <https://github.com/CodeGra-de/CodeGra.de/pull/399>`_
* Fix race condition in grade passback `(#409) <https://github.com/CodeGra-de/CodeGra.de/pull/409>`_
* Fix not catching errors caused by invalid files `(#410) <https://github.com/CodeGra-de/CodeGra.de/pull/410>`_
* Fix error when submitting for an LTI assignment without sourcedid `(#411) <https://github.com/CodeGra-de/CodeGra.de/pull/411>`_

**Packages Updates:**

* Upgrade NPM packages `(#370) <https://github.com/CodeGra-de/CodeGra.de/pull/370>`_

Version 0.22.1 (FlipFloppedWhiteSocked.2)
-------------------------------------------

**Released**: February 17th, 2018

**Fixes:**

* Make sure upload dialog is visible after deadline `(#375) <https://github.com/CodeGra-de/CodeGra.de/pull/375>`_

Version 0.21.5 (FlipFloppedWhiteSocked.1)
-----------------------------------------

**Released**: January 25th, 2018

**Fixes:**

* Fix assignment state buttons for LTI assignment `(#367) <https://github.com/CodeGra-de/CodeGra.de/pull/367>`_


Version 0.21.4 (FlipFloppedWhiteSocked)
----------------------------------------

**Released**: January 24th, 2018

**Features & Updates:**

* Make it possible to force reset of email when using LTI `(#347) <https://github.com/CodeGra-de/CodeGra.de/pull/347>`_
* Add done grading notification email `(#346) <https://github.com/CodeGra-de/CodeGra.de/pull/346>`_
* Make the way dividing and assigning works more intuitive `(#342) <https://github.com/CodeGra-de/CodeGra.de/pull/342>`_
* Email graders when their status is reset to not done `(#339) <https://github.com/CodeGra-de/CodeGra.de/pull/339>`_
* Add registration page `(#336) <https://github.com/CodeGra-de/CodeGra.de/pull/336>`_
* Split can manage course permission `(#319) <https://github.com/CodeGra-de/CodeGra.de/pull/319>`_
* Add autocomplete for adding students to a course `(#330) <https://github.com/CodeGra-de/CodeGra.de/pull/330>`_
* Add the first implementation of TA communication tools `(#313) <https://github.com/CodeGra-de/CodeGra.de/pull/313>`_
* Add the :kbd:`Ctrl+Enter` keybinding on the .cg-ignore field `(#329) <https://github.com/CodeGra-de/CodeGra.de/pull/329>`_
* Make it possible to reset password even if old password was NULL. `(#323) <https://github.com/CodeGra-de/CodeGra.de/pull/323>`_
* Add permission descriptions `(#312) <https://github.com/CodeGra-de/CodeGra.de/pull/312>`_

**Fixes:**

* Fix the reload behaviour of snippets `(#344) <https://github.com/CodeGra-de/CodeGra.de/pull/344>`_
* Make sure very large rubrics do not overflow the interface `(#343) <https://github.com/CodeGra-de/CodeGra.de/pull/343>`_
* Increase the speed of multiple routes and pages `(#332) <https://github.com/CodeGra-de/CodeGra.de/pull/332>`_ `(#341) <https://github.com/CodeGra-de/CodeGra.de/pull/341>`_
* Make sure the deadline object is cloned before modification `(#333) <https://github.com/CodeGra-de/CodeGra.de/pull/333>`_
* Make sure existing users are added to course during BB-zip upload `(#327) <https://github.com/CodeGra-de/CodeGra.de/pull/327>`_
* Make sure assignment title is only updated after submitting `(#328) <https://github.com/CodeGra-de/CodeGra.de/pull/328>`_
* Make sure a zip archive always contains a top level directory `(#324) <https://github.com/CodeGra-de/CodeGra.de/pull/324>`_
* Make sure a grade is always between 0 and 10 `(#326) <https://github.com/CodeGra-de/CodeGra.de/pull/326>`_
* Normalise API output `(#289) <https://github.com/CodeGra-de/CodeGra.de/pull/289>`_
* Communicate better that certain elements are clickable `(#278) <https://github.com/CodeGra-de/CodeGra.de/pull/278>`_
* Fix: "Files can be deleted even when they have comments associated with them" `(#307) <https://github.com/CodeGra-de/CodeGra.de/pull/307>`_
* Make sure grades are compared numerically if this is possible `(#309) <https://github.com/CodeGra-de/CodeGra.de/pull/309>`_
* Make blackboard zip regex handle more edge cases `(#280) <https://github.com/CodeGra-de/CodeGra.de/pull/280>`_

Version 0.16.9 (ExportHell)
----------------------------

**Released**: November 23rd, 2017

**Features & Updates:**

* Make it possible to give feedback without any grade `(#282) <https://github.com/CodeGra-de/CodeGra.de/pull/282>`_
* Make it possible to export username and user-id in csv `(#276) <https://github.com/CodeGra-de/CodeGra.de/pull/276>`_
* Add utils.formatGrade function to format grades with 2 decimals `(#264) <https://github.com/CodeGra-de/CodeGra.de/pull/264>`_
* Teacher revision interface `(#245) <https://github.com/CodeGra-de/CodeGra.de/pull/245>`_
* Add cgignore file `(#255) <https://github.com/CodeGra-de/CodeGra.de/pull/255>`_
* Add weight fields to submission divider `(#221) <https://github.com/CodeGra-de/CodeGra.de/pull/221>`_
* Courses actions buttons *nicefied* `(#247) <https://github.com/CodeGra-de/CodeGra.de/pull/247>`_

**Fixes:**

* Fix `null` in submission navbar `(#286) <https://github.com/CodeGra-de/CodeGra.de/pull/286>`_
* Fix various bugs with boolean parsing for sorting `(#285) <https://github.com/CodeGra-de/CodeGra.de/pull/285>`_
* Fix reset button on user info page `(#281) <https://github.com/CodeGra-de/CodeGra.de/pull/281>`_
* Make sure selected language is reseted if file is changed `(#283) <https://github.com/CodeGra-de/CodeGra.de/pull/283>`_
* Fix filter and order in submission navbar `(#268) <https://github.com/CodeGra-de/CodeGra.de/pull/268>`_
* Make sure ordering grades will work as expected `(#267) <https://github.com/CodeGra-de/CodeGra.de/pull/267>`_
* Fix makefile's phony targets `(#252) <https://github.com/CodeGra-de/CodeGra.de/pull/252>`_
* Make sure that the default config uses the application factory `(#253) <https://github.com/CodeGra-de/CodeGra.de/pull/253>`_
* Fix concurrent grade passback `(#251) <https://github.com/CodeGra-de/CodeGra.de/pull/251>`_
* Define media queries in the mixins file `(#248) <https://github.com/CodeGra-de/CodeGra.de/pull/248>`_
* Make sure comments or linters do not stop submission deletion `(#244) <https://github.com/CodeGra-de/CodeGra.de/pull/244>`_
* Redo LTI launch if it fails because of a 401 error `(#175) <https://github.com/CodeGra-de/CodeGra.de/pull/175>`_
* Put course list popovers above buttons instead of at the sides `(#250) <https://github.com/CodeGra-de/CodeGra.de/pull/250>`_
* Fix rubric-points colour in the dark theme when overridden `(#246) <https://github.com/CodeGra-de/CodeGra.de/pull/246>`_
* Make sure submissions can be deleted even if there is a grade history `(#242) <https://github.com/CodeGra-de/CodeGra.de/pull/242>`_
* Make sure sorting tables works as expected `(#240) <https://github.com/CodeGra-de/CodeGra.de/pull/240>`_
* Make sure blackboard zips with multiple files are uploaded correctly `(#239) <https://github.com/CodeGra-de/CodeGra.de/pull/239>`_

Version 0.12.6 (DobbeleJava)
----------------------------

**Released**: September 21st, 2017

**Features & Updates:**

* Add a dark theme to the website.
* Revamping exporting all submissions by making it possible to include feedback and fixed a bug that prevented the name of the grader to show.

**Fixes:**

* Fix bug that prevented downloading code of persons non `latin-1` characters in their names.
* Fix behaviour of next and previous buttons in the code viewer.
* Fix handling of long lines in the code viewer.
* Fix bug where a lot of grader change requests were done when changing filters on the submissions page.
* Fix html injection bugs.
* Make it possible to click on the login button again.
* Make sure underlines in the code viewer are only done on code, not on the feedback.
* Fix bootstrap Vue input fields not showing text.
* Fix bug that resulted in a large white space between the header and the body in LTI when dark mode is enabled.
* Fix bug that file tree viewer was way too long overlapping the footer.
* Fix bug that resulted in that every grade attempt showed as a new submission in the LMS.
* Fix bug that some floating point rubric items points resulted in very large descriptions overlapping the grade viewer.

Version 0.10.0 (Columbus)
--------------------------

**Released**: September 12th, 2017

**Features & Updates:**

* Make it possible for a user to reset its password `(#198) <https://github.com/CodeGra-de/CodeGra.de/pull/198>`_
* Allow to change font size and store it in vuex `(#191) <https://github.com/CodeGra-de/CodeGra.de/pull/191>`_
* Add a whitespace toggle button and language dropdown to the code viewer `(#95) <https://github.com/CodeGra-de/CodeGra.de/pull/95>`_
* Make it possible to disable incremental rubric submission `(#184) <https://github.com/CodeGra-de/CodeGra.de/pull/184>`_
* Add new course and assignment `(#186) <https://github.com/CodeGra-de/CodeGra.de/pull/186>`_
* Add global permission managing system `(#176) <https://github.com/CodeGra-de/CodeGra.de/pull/176>`_

**Fixes:**

* Fix jumping text when toggling directories in the file tree `(#199) <https://github.com/CodeGra-de/CodeGra.de/pull/199>`_
* Fix unicode errors while creating files. `(#197) <https://github.com/CodeGra-de/CodeGra.de/pull/197>`_
* Make rubric deletion also not save directly when incremental rubric submission is off `(#192) <https://github.com/CodeGra-de/CodeGra.de/pull/192>`_
* Fix various filesystem api bugs `(#187) <https://github.com/CodeGra-de/CodeGra.de/pull/187>`_
* Fix file-links in the code viewer `(#189) <https://github.com/CodeGra-de/CodeGra.de/pull/189>`_
* Fix undefined error on submission page `(#190) <https://github.com/CodeGra-de/CodeGra.de/pull/190>`_
* Fix a bug where files would be left open after submitting archive `(#188) <https://github.com/CodeGra-de/CodeGra.de/pull/188>`_
* Remove item description popover `(#179) <https://github.com/CodeGra-de/CodeGra.de/pull/179>`_
* Make sure global permissions are checked in the front- and back-end `(#177) <https://github.com/CodeGra-de/CodeGra.de/pull/177>`_
* Fix issue where error would disappear immediately after submitting with the keyboard `(#180) <https://github.com/CodeGra-de/CodeGra.de/pull/180>`_

**Packages Updates:**

* Upgrade bootstrap-vue `(#200) <https://github.com/CodeGra-de/CodeGra.de/pull/200>`_

Version 0.3.2 (Belhamel)
-------------------------

**Released**: September 4th, 2017

**Features & Updates:**

* Add delete submission feature `(#166) <https://github.com/CodeGra-de/CodeGra.de/pull/166>`_
* Add privacy notes `(#169) <https://github.com/CodeGra-de/CodeGra.de/pull/169>`_
* Update rubric selector and creator front end `(#154) <https://github.com/CodeGra-de/CodeGra.de/pull/154>`_
* Make it possible to upload files by dragging and dropping `(#164) <https://github.com/CodeGra-de/CodeGra.de/pull/164>`_
* Make it possible to disable automatic LTI role creation `(#158) <https://github.com/CodeGra-de/CodeGra.de/pull/158>`_
* Add codecov as coverage reporter `(#160) <https://github.com/CodeGra-de/CodeGra.de/pull/160>`_
* Change submission assignee from submissions list `(#152) <https://github.com/CodeGra-de/CodeGra.de/pull/152>`_
* Add documentation for how to run CodeGra.de `(#130) <https://github.com/CodeGra-de/CodeGra.de/pull/130>`_
* Add grade history `(#149) <https://github.com/CodeGra-de/CodeGra.de/pull/149>`_
* Sort rubric items in the rubric viewer `(#146) <https://github.com/CodeGra-de/CodeGra.de/pull/146>`_
* Improve site navigation `(#145) <https://github.com/CodeGra-de/CodeGra.de/pull/145>`_
* Make it possible to delete a grade `(#138) <https://github.com/CodeGra-de/CodeGra.de/pull/138>`_
* Make it possible to submit non integer grades `(#137) <https://github.com/CodeGra-de/CodeGra.de/pull/137>`_
* Autofocus username field on login page `(#133) <https://github.com/CodeGra-de/CodeGra.de/pull/133>`_
* Allow to update name and deadline of an assignment separately `(#118) <https://github.com/CodeGra-de/CodeGra.de/pull/118>`_
* Make it possible again to grade work `(#125) <https://github.com/CodeGra-de/CodeGra.de/pull/125>`_
* Make duplicate emails possible `(#116) <https://github.com/CodeGra-de/CodeGra.de/pull/116>`_

**Fixes:**

* Fix all missing or wrong quickrefs on api calls `(#172) <https://github.com/CodeGra-de/CodeGra.de/pull/172>`_
* Fix stat api route `(#163) <https://github.com/CodeGra-de/CodeGra.de/pull/163>`_
* Fix graders list of an assignment being loaded without correct permissions `(#157) <https://github.com/CodeGra-de/CodeGra.de/pull/157>`_
* Fix bug where only the second LTI launch would work `(#151) <https://github.com/CodeGra-de/CodeGra.de/pull/151>`_
* Fix front-end feature usage `(#144) <https://github.com/CodeGra-de/CodeGra.de/pull/144>`_
* Clear vuex cache on :kbd:`Ctrl+F5` `(#134) <https://github.com/CodeGra-de/CodeGra.de/pull/134>`_
* Fix timezone issues on a LTI launch with deadline info `(#127) <https://github.com/CodeGra-de/CodeGra.de/pull/127>`_
* Make sure all test files are directories `(#132) <https://github.com/CodeGra-de/CodeGra.de/pull/132>`_
* Fix course link on assignment page `(#126) <https://github.com/CodeGra-de/CodeGra.de/pull/126>`_
* Fix downloading files from server `(#124) <https://github.com/CodeGra-de/CodeGra.de/pull/124>`_
* Fix unknown LTI roles `(#121) <https://github.com/CodeGra-de/CodeGra.de/pull/121>`_
* Fix undefined issues in LTI environments `(#123) <https://github.com/CodeGra-de/CodeGra.de/pull/123>`_
* Add test-generated files to gitignore `(#119) <https://github.com/CodeGra-de/CodeGra.de/pull/119>`_
* Fix seed_data and test_data paths `(#120) <https://github.com/CodeGra-de/CodeGra.de/pull/120>`_
* Create update api `(#108) <https://github.com/CodeGra-de/CodeGra.de/pull/108>`_
* Rewrite submission page `(#87) <https://github.com/CodeGra-de/CodeGra.de/pull/87>`_
* Fix bugs introduced by postgres `(#109) <https://github.com/CodeGra-de/CodeGra.de/pull/109>`_
* Add links to them fine shields `(#104) <https://github.com/CodeGra-de/CodeGra.de/pull/104>`_

**Package Updates:**

* Remove pdfobject and pdf.js dependencies `(#159) <https://github.com/CodeGra-de/CodeGra.de/pull/159>`_
* Move bootstrap-vue dependency to own org `(#142) <https://github.com/CodeGra-de/CodeGra.de/pull/142>`_
* Add npm-shrinkwrap.json and delete yarn.lock `(#141) <https://github.com/CodeGra-de/CodeGra.de/pull/141>`_
* Change to JWT tokens `(#105) <https://github.com/CodeGra-de/CodeGra.de/pull/105>`_

Version 0.2.0 (Alfa)
---------------------

**Released**: July 21st, 2017

Initial CodeGrade release
