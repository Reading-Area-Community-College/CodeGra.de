<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader center v-if="loadingPage"/>
<div class="page submission outer-container" id="submission-page" v-else>
    <b-modal id="modal_delete" title="Are you sure?" :hide-footer="true">
        <p style="text-align: center;">
            By deleting all information about this submission,
            including files, will be lost forever! So are you
            really sure?
        </p>
        <b-button-toolbar justify>
            <submit-button ref="deleteButton"
                           default="outline-danger"
                           @click="deleteSubmission"
                           label="Yes"/>
            <b-btn class="text-center"
                   variant="success"
                   @click="$root.$emit('bv::hide::modal', `modal_delete`)">
                No!
            </b-btn>
        </b-button-toolbar>
    </b-modal>

    <local-header :back-route="submissionsRoute"
                  back-popover="Go back to submissions list">
        <submission-nav-bar v-if="submissions"
                            v-model="submission"
                            :submissions="submissions"
                            :filter="filterSubmissions"/>

        <b-input-group class="submission-header-buttons">
            <b-input-group-append v-if="canSeeFeedback">
                <b-button class="overview-btn"
                          :variant="overviewMode ? 'primary' : 'secondary'"
                          @click="toggleOverviewMode(false)"
                          v-b-popover.bottom.hover="'Toggle overview mode'"
                          id="codeviewer-overview-toggle">
                    <icon name="binoculars"/>
                </b-button>
            </b-input-group-append>

            <b-input-group-append>
                <b-button class="settings-toggle"
                          v-b-popover.hover.top="'Edit settings'"
                          id="codeviewer-settings-toggle">
                    <icon name="cog"/>
                </b-button>
                <b-popover triggers="click"
                           class="settings-popover"
                           target="codeviewer-settings-toggle"
                           @show="beforeShowPopover"
                           container="#submission-page"
                           placement="bottom">
                    <div class="settings-content"
                         id="codeviewer-settings-content"
                         ref="settingsContent">
                        <preference-manager :file-id="(currentFile && currentFile.id) || `${submission.id}-OVERVIEW`"
                                            :show-revision="canSeeRevision && !overviewMode"
                                            :show-language="!(diffMode || overviewMode)"
                                            :show-context-amount="overviewMode"
                                            :revision="selectedRevision"
                                            @context-amount="contextAmountChanged"
                                            @whitespace="whitespaceChanged"
                                            @language="languageChanged"
                                            @font-size="fontSizeChanged"
                                            @revision="revisionChanged"/>
                    </div>
                </b-popover>
            </b-input-group-append>

            <b-input-group-append v-if="editable || assignment.state === assignmentState.DONE">
                <b-button id="codeviewer-general-feedback"
                          :variant="warnComment ? 'warning' : undefined"
                          v-b-popover.hover.top="`${editable ? 'Edit' : 'Show'} general feedback`">
                    <icon name="edit"/>
                </b-button>
                <b-popover target="codeviewer-general-feedback"
                           :title="`General feedback${submission.comment_author ? ' by ' + submission.comment_author.name : ''}`"
                           triggers="click"
                           container="#submission-page"
                           @show="beforeShowPopover"
                           placement="bottom">
                    <general-feedback-area style="width: 35em;"
                                           @updated="generalFeedbackUpdated"
                                           :submission="submission"
                                           :editable="editable"/>
                </b-popover>
            </b-input-group-append>

            <b-input-group-append v-if="gradeHistory">
                <b-button id="codeviewer-grade-history"
                          v-b-popover.hover.top="'Grade history'">
                    <icon name="history"/>
                </b-button>
                <!--
                    We need `overflow-x: hidden` to make sure the popover is
                    displayed correctly, however this breaks the `sticky` header
                    so we simply display it differently if we need this
                    sticky header.
                    TODO: make the `isLargeWindow` reactive.
                  -->
                <b-popover target="codeviewer-grade-history"
                           title="Grade history"
                           triggers="click"
                           container="#submission-page"
                           @show="beforeShowPopover(); $refs.gradeHistory.updateHistory()"
                           :placement="$root.$isLargeWindow || $root.$isSmallWindow ? 'bottom' : 'left'">
                    <grade-history ref="gradeHistory"
                                   :submissionId="submission.id"
                                   :isLTI="assignment.course.is_lti"/>
                </b-popover>
            </b-input-group-append>

            <b-input-group-append>
                <b-button v-b-popover.hover.top="'Download assignment or feedback'"
                          id="codeviewer-download-toggle">
                    <icon name="download"/>
                </b-button>
                <b-popover target="codeviewer-download-toggle"
                           triggers="click"
                           @show="beforeShowPopover"
                           placement="bottom">
                    <b-button @click="downloadType('zip')"
                              variant="primary">
                        Archive
                    </b-button>

                    <b-button v-if="canSeeFeedback"
                              @click="downloadType('feedback')"
                              variant="primary">
                        Feedback
                    </b-button>
                </b-popover>
            </b-input-group-append>

            <b-input-group-append v-if="canDeleteSubmission">
                <b-btn class="text-center"
                       variant="danger"
                       v-b-popover.hover.top="'Delete submission'"
                       @click="$root.$emit('bv::show::modal',`modal_delete`)">
                    <icon name="times"/>
                </b-btn>
            </b-input-group-append>
        </b-input-group>
    </local-header>

    <loader center v-if="loadingInner"/>
    <div class="row inner-container"
         v-else
         id="submission-page-inner">
        <div class="code-and-grade"
             :class="overviewMode ?  'overview col-md-12' : 'col-md-9'">

            <div v-if="!fileTree || !currentFile" class="no-file">
                <loader/>
            </div>
            <b-alert show
                     class="error no-file"
                     variant="danger"
                     v-else-if="fileTree.entries.length === 0">
                No files found!
            </b-alert>
            <overview-mode v-else-if="overviewMode"
                           :assignment="assignment"
                           :submission="submission"
                           :tree="fileTree"
                           :context="contextAmount"
                           :teacher-tree="teacherTree"
                           :can-see-revision="canSeeRevision"
                           :font-size="fontSize"
                           :show-whitespace="showWhitespace"/>
            <pdf-viewer :id="currentFile.id"
                        v-else-if="currentFile.extension === 'pdf'"/>
            <image-viewer :id="currentFile.id"
                          :name="currentFile.name"
                          v-else-if="/^(?:gif|jpe?g|png|svg)$/.test(currentFile.extension)"/>
            <diff-viewer v-else-if="selectedRevision === 'diff' && currentFile.ids[0] !== currentFile.ids[1]"
                         :file="currentFile"
                         :font-size="fontSize"
                         :show-whitespace="showWhitespace"/>
            <code-viewer v-else
                         :assignment="assignment"
                         :submission="submission"
                         :file="currentFile"
                         :editable="editable && studentMode"
                         :tree="fileTree"
                         :font-size="fontSize"
                         :show-whitespace="showWhitespace"
                         @new-lang="languageChanged"
                         :language="selectedLanguage"/>

            <grade-viewer :assignment="assignment"
                          :submission="submission"
                          :rubric="rubric"
                          :editable="editable"
                          v-if="editable || assignment.state === assignmentState.DONE"
                          @gradeUpdated="gradeUpdated"/>
        </div>

        <div class="col-md-3 file-tree-container" v-if="!overviewMode">
            <loader class="text-center"
                    :scale="3"
                    v-if="!fileTree"/>
            <file-tree v-else
                       :collapsed="false"
                       :tree="fileTree"/>
        </div>
    </div>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/download';
import 'vue-awesome/icons/edit';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/exclamation-triangle';
import 'vue-awesome/icons/history';
import 'vue-awesome/icons/binoculars';

import { mapGetters } from 'vuex';

import { filterSubmissions, cmpNoCase, formatGrade, parseBool } from '@/utils';

import {
    CodeViewer,
    DiffViewer,
    FileTree,
    GradeViewer,
    GradeHistory,
    GeneralFeedbackArea,
    ImageViewer,
    Loader,
    LocalHeader,
    PdfViewer,
    PreferenceManager,
    SubmissionNavBar,
    SubmitButton,
    Toggle,
    OverviewMode,
} from '@/components';

import * as assignmentState from '@/store/assignment-states';

import { setPageTitle } from '@/pages/title';


export default {
    name: 'submission-page',

    data() {
        let forceInclude = new Set();
        try {
            forceInclude = new Set(JSON.parse(this.$route.query.forceInclude));
        } catch (e) {
            // NOT EMPTY
        }

        return {
            courseId: Number(this.$route.params.courseId),
            assignmentId: Number(this.$route.params.assignmentId),
            assignment: null,
            submissionId: Number(this.$route.params.submissionId),
            submission: null,
            fileTree: null,
            studentTree: null,
            teacherTree: null,
            currentFile: null,
            submissions: null,
            rubric: null,
            loadingPage: true,
            loadingInner: true,
            canDeleteSubmission: false,
            initialLoad: true,
            assignmentState,
            canSeeFeedback: false,
            canSeeRevision: false,
            showWhitespace: true,
            fontSize: 12,
            contextAmount: 3,
            selectedLanguage: 'Default',
            gradeHistory: true,
            forceInclude,
            submissionChangedByRoute: false,
        };
    },

    computed: {
        ...mapGetters({
            nameCurrentUser: 'user/name',
        }),

        studentMode() {
            return this.$route.query.revision === 'student';
        },

        diffMode() {
            return this.$route.query.revision === 'diff';
        },

        warnComment() {
            return !this.editable &&
                this.assignment.state === assignmentState.DONE &&
                this.submission.comment !== '';
        },

        overviewMode() {
            return this.canSeeFeedback && parseBool(this.$route.query.overview, false);
        },

        selectedRevision() {
            return this.$route.query.revision || 'student';
        },

        submissionsRoute() {
            return {
                name: 'assignment_submissions',
                params: {
                    courseId: this.$route.params.courseId,
                    assignmentId: this.$route.params.assignmentId,
                },
                query: {
                    q: this.$route.query.search || undefined,
                    mine: this.$route.query.mine || false,
                    latest: this.$route.query.latest || false,
                    sortBy: this.$route.query.sortBy,
                    sortAsc: this.$route.query.sortAsc,
                },
            };
        },
    },

    watch: {
        overviewMode() {
            this.selectFileTree();
        },

        assignment() {
            if (this.submission) {
                this.$nextTick(this.updateTitle);
            }
            if (this.assignment.state === assignmentState.DONE &&
                !Object.hasOwnProperty.call(this.$route.query, 'overview')) {
                this.toggleOverviewMode(true);
            }
        },

        submission(submission) {
            if (submission.id === this.submissionId) {
                this.initialLoad = false;
                return;
            }

            this.submissionId = submission.id;
            if (!this.initialLoad) {
                this.fileTree = null;
                this.currentFile = null;
                this.setRevision('student');
            }

            if (this.assignment) {
                this.$nextTick(this.updateTitle);
            }

            this.loadingInner = true;
            this.getSubmissionData().then(() => {
                this.loadingInner = false;
            });

            if (!this.initialLoad && !this.submissionChangedByRoute) {
                this.$router.push({
                    name: 'submission',
                    params: {
                        courseId: this.courseId,
                        assignmentId: this.assignmentId,
                        submissionId: submission.id,
                    },
                    query: Object.assign({}, this.$route.query, {
                        overview: this.assignment.state === assignmentState.DONE,
                    }),
                });
            }

            this.submissionChangedByRoute = false;
            this.initialLoad = false;
        },

        $route(to) {
            const fileId = Number(to.params.fileId);
            const submissionId = Number(to.params.submissionId);

            if (this.submissionId.toString() !== submissionId.toString()) {
                this.submissionChangedByRoute = true;
                this.submission = this.submissions.find(
                    sub => sub.id === submissionId,
                );
            }

            if (this.fileTree && (this.currentFile == null || fileId !== this.currentFile.id)) {
                this.currentFile = this.searchTree(this.fileTree, fileId);
            }

            this.$nextTick(this.updateTitle);
        },

        fileTree(treeTo) {
            if (treeTo == null) {
                return;
            }
            let fileId = Number(this.$route.params.fileId);

            let file;
            if (fileId) {
                file = this.searchTree(treeTo, fileId);
                if (file == null && this.currentFile != null && this.currentFile.revision != null) {
                    file = this.searchTree(treeTo, this.currentFile.revision.id);
                }
            }

            if (file == null) {
                file = this.getFirstFile(treeTo);
            }

            if (file != null) {
                if (this.currentFile == null || this.currentFile.id !== file.id) {
                    this.currentFile = file;
                }

                fileId = file.id || (file.ids && (file.ids[0] || file.ids[1]));
                this.$router.replace({
                    name: 'submission_file',
                    params: { fileId },
                    query: Object.assign(
                        {},
                        this.$route.query,
                        { revision: this.selectedRevision },
                    ),
                });
                this.$nextTick(this.updateTitle);
            }
        },

        currentFile(file) {
            if (file != null) {
                file.extension = '';
                const nameparts = file.name.split('.');
                if (nameparts.length > 1) {
                    file.extension = nameparts[nameparts.length - 1];
                }
            }
        },
    },

    mounted() {
        Promise.all([
            this.$hasPermission(
                [
                    'can_grade_work',
                    'can_see_grade_before_open',
                    'can_delete_submission',
                    'can_view_own_teacher_files',
                    'can_edit_others_work',
                    'can_see_grade_history',
                ],
                this.courseId,
            ),
            this.getAssignment(),
            this.getAllSubmissions(),
            this.getSubmissionData(),
        ]).then(([[
            canGrade,
            canSeeGrade,
            canDeleteSubmission,
            ownTeacher,
            editOthersWork,
            canSeeGradeHistory,
        ]]) => {
            this.editable = canGrade;
            this.canSeeFeedback = canSeeGrade ||
                (this.assignment.state === assignmentState.DONE);
            this.canDeleteSubmission = canDeleteSubmission;
            this.gradeHistory = canSeeGradeHistory;

            if (this.$store.getters['user/id'] === this.submission.user.id &&
                this.assignment.state === assignmentState.DONE) {
                this.canSeeRevision = ownTeacher;
            } else {
                this.canSeeRevision = editOthersWork;
            }

            this.loadingPage = false;
            this.loadingInner = false;
        });
    },

    methods: {
        generalFeedbackUpdated(val) {
            this.submission.comment = val;
            this.submission.comment_author = { name: this.nameCurrentUser };
        },

        setRevision(val) {
            this.$router.push({
                name: this.$route.params.fileId ? 'submission_file' : 'submission',
                params: this.$route.params,
                query: Object.assign(
                    {},
                    this.$route.query,
                    { revision: val },
                ),
            });
        },

        updateTitle() {
            if (!this.assignment) {
                return;
            }

            let title = this.assignment.name;
            if (this.submission) {
                title += ` by ${this.submission.user.name}`;
                if (this.submission.grade) {
                    title += ` (${formatGrade(this.submission.grade)})`;
                }
            }
            setPageTitle(title);
        },

        beforeShowPopover() {
            this.$root.$emit('bv::hide::popover');
        },

        getAssignment() {
            return this.$http.get(`/api/v1/assignments/${this.assignmentId}`).then(({ data: assignment }) => {
                this.assignment = assignment;
            });
        },

        getAllSubmissions() {
            return this.$http.get(`/api/v1/assignments/${this.assignmentId}/submissions/?extended`).then(({ data: submissions }) => {
                this.submissions = submissions;
                this.submission = submissions.find(sub =>
                    sub.id === this.submissionId);
            });
        },

        toggleOverviewMode(forceOn = false) {
            this.$router.push({
                query: Object.assign(
                    {},
                    this.$route.query,
                    { overview: forceOn || !this.overviewMode },
                ),
            });
        },

        deleteSubmission() {
            const req = this.$http.delete(`/api/v1/submissions/${this.submissionId}`);

            this.$refs.deleteButton.submit(req.catch((err) => {
                throw err.response.data.message;
            })).then(() => {
                this.$router.push({
                    name: 'assignment_submissions',
                    params: {
                        courseId: this.assignment.course.id,
                        assignmentId: this.assignment.id,
                    },
                });
            });
        },

        getSubmissionData() {
            return Promise.all([
                this.getFileTrees(),
                this.getRubric(),
            ]);
        },

        getFileTrees() {
            return Promise.all([
                this.$http.get(`/api/v1/submissions/${this.submissionId}/files/`),
                this.$http.get(`/api/v1/submissions/${this.submissionId}/files/?owner=teacher`)
                    .catch(() => null),
            ]).then(([student, teacher]) => {
                this.studentTree = student.data;
                this.studentTree.isStudent = true;
                if (teacher != null) {
                    this.teacherTree = teacher.data;
                    this.teacherTree.isTeacher = true;
                    this.diffTree = this.matchFiles(this.studentTree, this.teacherTree);
                    this.diffTree.isDiff = true;
                } else {
                    this.diffTree = this.matchFiles(this.studentTree, this.studentTree);
                }
                this.selectFileTree();
            });
        },

        matchFiles(tree1, tree2) {
            const diffTree = {
                name: tree1.name,
                entries: [],
                push(ids, name) { this.entries.push({ ids, name }); },
            };

            const lookupTree2 = tree2.entries.reduce((accum, cur) => {
                accum[cur.name] = Object.assign({}, cur, { done: false });
                return accum;
            }, {});

            tree1.entries.forEach((self) => {
                const other = lookupTree2[self.name];

                if (other == null) {
                    self.revision = null;
                    diffTree.push([self.id, null], self.name);
                    return;
                }

                other.done = true;

                if (self.id !== other.id) {
                    self.revision = other;
                    other.revision = self;
                }

                if (self.entries && other.entries) {
                    diffTree.entries.push(this.matchFiles(self, other));
                } else if (self.entries == null && other.entries == null) {
                    diffTree.push([self.id, other.id], self.name);
                } else if (self.entries) {
                    diffTree.push([null, other.id], other.name);
                    diffTree.entries.push(this.matchFiles(self, {
                        name: self.name,
                        entries: [],
                    }));
                } else if (other.entries) {
                    diffTree.push([self.id, null], self.name);
                    diffTree.entries.push(this.matchFiles({
                        name: other.name,
                        entries: [],
                    }, other));
                }
            });

            Object.values(lookupTree2).forEach((val) => {
                if (val.done) {
                    return;
                }
                if (val.entries) {
                    diffTree.entries.push(this.matchFiles({
                        name: val.name,
                        entries: [],
                    }, val));
                } else {
                    diffTree.push([null, val.id], val.name);
                }
            });

            diffTree.entries.sort((a, b) => {
                if (a.name === b.name) {
                    return a.entries ? -1 : 1;
                }
                return cmpNoCase(a.name, b.name);
            });

            delete diffTree.push;
            return diffTree;
        },

        getRubric() {
            if (!UserConfig.features.rubrics) {
                return Promise.resolve(null);
            }
            return this.$http.get(`/api/v1/submissions/${this.submissionId}/rubrics/`).then(({ data: rubric }) => {
                this.rubric = rubric;
            }, () => null);
        },

        // Returns the first file in the file tree that is not a folder
        // The file tree is searched with BFS
        getFirstFile(fileTree) {
            const queue = [fileTree];
            let candidate = null;

            while (queue.length > 0) {
                candidate = queue.shift();

                if (candidate.entries) {
                    queue.push(...candidate.entries);
                } else {
                    return candidate;
                }
            }

            return null;
        },

        // Search the tree for the file with the givven id.
        searchTree(tree, id) {
            for (let i = 0; i < tree.entries.length; i += 1) {
                const child = tree.entries[i];
                if ((child.id === id || (child.revision && child.revision.id === id)) ||
                    (child.ids && (child.ids[0] === id || child.ids[1] === id))) {
                    return child;
                } else if (child.entries != null) {
                    const match = this.searchTree(child, id);
                    if (match != null) {
                        return match;
                    }
                }
            }
            return null;
        },

        filterSubmissions(submissions) {
            const userId = this.$store.state.user.id;
            const filterLatest = parseBool(this.$route.query.latest, true);
            const filterAssignee = parseBool(this.$route.query.mine, true);

            const checkReally = (sub) => {
                if (this.forceInclude.has(sub.id)) {
                    return true;
                }

                if (this.submissionId === sub.id) {
                    this.forceInclude.add(sub.id);
                    this.$router.replace({
                        query: Object.assign(
                            {},
                            this.$route.query,
                            { forceInclude: JSON.stringify([...this.forceInclude]) },
                        ),
                    });
                    this.$nextTick(this.updateTitle);
                    return true;
                }
                return false;
            };

            return filterSubmissions(
                submissions,
                filterLatest,
                filterAssignee,
                userId,
                this.$route.query.search,
                checkReally,
            );
        },

        downloadType(type) {
            this.$http.get(`/api/v1/submissions/${this.submissionId}?type=${type}`).then(({ data }) => {
                const params = new URLSearchParams();
                params.append('not_as_attachment', '');
                window.open(`/api/v1/files/${data.name}/${data.output_name}?${params.toString()}`);
            });
        },

        gradeUpdated(grade) {
            this.$set(this.submission, 'grade', grade);
            if (this.submissions) {
                this.$set(
                    this.submissions, this.submissions.indexOf(this.submission),
                    this.submission,
                );
            }
        },

        whitespaceChanged(val) {
            this.showWhitespace = val;
        },

        languageChanged(val) {
            this.selectedLanguage = val;
        },

        contextAmountChanged(val) {
            this.contextAmount = val;
        },

        fontSizeChanged(val) {
            this.fontSize = val;
        },

        revisionChanged(val) {
            this.setRevision(val);
            this.selectFileTree();
        },

        selectFileTree() {
            if (this.overviewMode) {
                this.fileTree = this.diffTree;
                return;
            }

            switch (this.selectedRevision) {
            case 'teacher':
                this.fileTree = this.teacherTree;
                break;
            case 'diff':
                this.fileTree = this.diffTree;
                break;
            case 'student':
            default:
                this.fileTree = this.studentTree;
                break;
            }
        },
    },

    components: {
        CodeViewer,
        DiffViewer,
        FileTree,
        GradeViewer,
        GradeHistory,
        GeneralFeedbackArea,
        ImageViewer,
        Loader,
        LocalHeader,
        PdfViewer,
        PreferenceManager,
        SubmissionNavBar,
        SubmitButton,
        Toggle,
        Icon,
        OverviewMode,
    },
};
</script>

<style lang="less" scoped>
@import "~mixins.less";

.outer-container {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    height: 100vh;
    max-height: 100%;
    margin-bottom: 0 !important;
}

.inner-container {
    flex: 1 1 auto;
    flex-wrap: nowrap;
    min-height: 0;

    @media @media-no-large {
        flex-direction: column;
        justify-content: start !important;
    }
}

.submission-nav-bar {
    flex: 1 1 auto;
    margin-right: 15px;
}

.code-and-grade {
    position: relative;
    display: flex;
    flex-direction: column;
    max-height: 100%;

    @media @media-no-large {
        flex: 0 1 auto;
    }
}

.pdf-viewer {
    flex: 1 1 auto;
    min-height: 0;

    @media @media-no-large {
        flex: 1 1 100vh;
    }
}

.image-viewer {
    flex: 0 1 auto;
    min-height: 0;
}

.code-viewer,
.overview-mode,
.diff-viewer {
    overflow: auto;

    // Fixes performance issues on scrolling because the entire
    // code viewer isn't repainted anymore.
    will-change: transform;

    @media @media-no-large {
        flex: 1 1 auto;
        flex: 1 1 -webkit-max-content;
        flex: 1 1 -moz-max-content;
        flex: 1 1 max-content;
    }
}

.grade-viewer {
    flex: 0 0 auto;
}

.no-file,
.overview-mode,
.code-viewer,
.diff-viewer,
.pdf-viewer,
.image-viewer,
.file-tree-container {
    margin-bottom: 1rem;
}

.overview-mode {
    padding: 0;
}

.file-tree-container {
    flex-direction: column;

    @media @media-no-large {
        flex: 0 0 auto;
    }
}

.file-tree {
    max-height: 100%;
    overflow: auto;

    @media @media-no-large {
        max-height: 15vh;
    }
}

.loader {
    margin-top: 1em;
}

.submission-header-buttons {
    .input-group-append:first-child button:first-of-type {
        border-top-left-radius: .25rem;
        border-bottom-left-radius: .25rem;
    }

    .input-group-append:last-child button:last-of-type {
        border-top-right-radius: .25rem;
        border-bottom-right-radius: .25rem;
    }
}
</style>

<style lang="less">
#submission-page .popover {
    max-width: 45em;
}
</style>
