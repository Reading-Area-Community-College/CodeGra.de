<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="submission-list">
    <local-header always-show-extra-slot>
        <template slot="title" v-if="assignment && Object.keys(assignment).length">
            {{ assignment.name }}

            <small v-if="assignment.formatted_deadline">- due {{ assignment.formatted_deadline }}</small>
            <small v-else class="text-muted"><i>- No deadline</i></small>
        </template>

        <template slot="extra">
            <hr class="separator top-separator"/>

            <category-selector slot="extra"
                               :default="defaultCat"
                               v-model="selectedCat"
                               :categories="categories"/>

            <hr class="separator bottom-separator"/>

            <div class="cat-container">
                <b-input-group v-if="selectedCat === 'Search'"
                               class="search-wrapper">
                    <input v-model="filter"
                           class="form-control"
                           placeholder="Type to Search"
                           @keyup.enter="submit"
                           @keyup="submitDelayed"/>

                    <b-input-group-append is-text
                                          v-b-popover.bottom.hover="'Show only the latest submission of each student.'">
                        <b-form-checkbox v-model="latestOnly"
                                         @change="submit">
                            Latest only
                        </b-form-checkbox>
                    </b-input-group-append>

                    <b-input-group-append is-text
                                          v-b-popover.bottom.hover="'Show only subbmissions assigned to me.'">
                        <b-form-checkbox v-model="mineOnly" @change="submit">
                            Assigned to me
                        </b-form-checkbox>
                    </b-input-group-append>
                </b-input-group>

                <div v-if="selectedCat === 'Rubric'">
                    <rubric-editor v-if="assignment.rubric != null"
                                   :editable="false"
                                   :defaultRubric="rubric"
                                   :assignment="assignment"/>
                    <div no-body class="empty-text text-muted font-italic" v-else>
                        There is no rubric for this assignment.
                    </div>
                </div>

                <div v-if="selectedCat === 'Hand-in instructions'">
                    <c-g-ignore-file v-if="assignment.cgignore"
                                     :assignmentId="assignment.id"
                                     :editable="false"
                                     summary-mode/>
                    <div no-body class="empty-text text-muted font-italic" v-else>
                        There are no hand-in instructions for this assignment.
                    </div>
                </div>

                <submissions-exporter v-if="selectedCat === 'Export'"
                                      :get-submissions="filter => filter ? filteredSubmissions : submissions"
                                      :assignment-id="assignment.id"
                                      :filename="exportFilename"/>
            </div>
        </template>

        <b-input-group>
            <b-button-group>
                <b-button :to="manageAssignmentRoute"
                          variant="secondary"
                          v-if="assignment.canManage"
                          v-b-popover.bottom.hover="'Manage assignment'">
                    <icon name="gear"/>
                </b-button>
                <submit-button :wait-at-least="500"
                               :submit="submitForceLoadSubmissions"
                               v-b-popover.bottom.hover="'Reload submissions'">
                    <icon name="refresh"/>
                    <icon name="refresh" spin slot="pending-label"/>
                </submit-button>
            </b-button-group>
        </b-input-group>
    </local-header>

    <b-table striped hover
             ref="table"
             @row-clicked="gotoSubmission"
             @sort-changed="(ctx) => $nextTick(() => sortChanged(ctx))"
             :items="filteredSubmissions"
             :fields="fields"
             :current-page="currentPage"
             :sort-compare="sortSubmissions"
             :sort-by="this.$route.query.sortBy || 'user'"
             :sort-desc="!parseBool(this.$route.query.sortAsc, true)"
             class="submissions-table">
        <a class="invisible-link"
           href="#"
           slot="user"
           slot-scope="item"
           @click.prevent>
            <user :user="item.value"/>
        </a>

        <template slot="grade" slot-scope="item">
            {{formatGrade(item.value) || '-'}}
        </template>

        <template slot="formatted_created_at" slot-scope="item">
            {{item.value ? item.value : '-'}}
            <span v-if="item.item.created_at > assignment.deadline">
                <icon name="clock-o"
                      class="late-icon"
                      v-b-popover.hover.top="getHandedInLateText(item.item)"/>
            </span>
        </template>

        <template slot="assignee" slot-scope="item">
            <span v-if="!canAssignGrader || graders == null">
                <user :user="item.value" v-if="item.value"/>
                <span v-else>-</span>
            </span>
            <loader :scale="1" v-else-if="assigneeUpdating[item.item.id]"/>
            <b-form-select :options="assignees"
                           :value="item.value ? item.value.id : null"
                           @input="updateAssignee($event, item)"
                           @click.native.stop
                           style="max-width: 20em; margin: -.35rem 0;"
                           v-else/>
        </template>
    </b-table>

    <div class="submission-count">
        Showing {{ filteredSubmissions.length }} of a total of {{ submissions.length }}
        submissions by {{ numFilteredStudents }} out of {{ numStudents }}
        students.
    </div>
</div>
</template>

<script>
import moment from 'moment';
import { mapGetters, mapActions } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/gear';
import 'vue-awesome/icons/refresh';
import 'vue-awesome/icons/clock-o';

import { waitAtLeast, formatGrade, parseBool, nameOfUser } from '@/utils';
import { filterSubmissions, sortSubmissions } from '@/utils/FilterSubmissionsManager';

import * as assignmentState from '@/store/assignment-states';
import SubmissionsExporter from './SubmissionsExporter';
import Loader from './Loader';
import SubmitButton from './SubmitButton';
import RubricEditor from './RubricEditor';
import LocalHeader from './LocalHeader';
import User from './User';
import CategorySelector from './CategorySelector';
import CGIgnoreFile from './CGIgnoreFile';

export default {
    name: 'submission-list',

    props: {
        assignment: {
            type: Object,
            default: null,
        },
        submissions: {
            type: Array,
            default: [],
        },
        canDownload: {
            type: Boolean,
            default: false,
        },
        rubric: {
            default: null,
        },
        graders: {
            default: null,
            type: Array,
        },
        canSeeAssignee: {
            type: Boolean,
            required: true,
        },
        canAssignGrader: {
            type: Boolean,
            required: false,
        },
        canSeeOthersWork: {
            type: Boolean,
            required: false,
        },
    },

    data() {
        return {
            parseBool,
            latestOnly: parseBool(this.$route.query.latest, true),
            mineOnly: parseBool(this.$route.query.mine, null),
            currentPage: 1,
            filter: this.$route.query.q || '',
            latest: this.getLatest(this.submissions),
            assignees: [],
            assigneeUpdating: [],
            selectedCat: '',
        };
    },

    computed: {
        ...mapGetters('user', {
            userId: 'id',
            userName: 'name',
        }),

        fields() {
            const fields = [
                {
                    key: 'user',
                    label: 'User',
                    sortable: true,
                },
                {
                    key: 'grade',
                    label: 'Grade',
                    sortable: true,
                },
                {
                    key: 'formatted_created_at',
                    label: 'Created at',
                    sortable: true,
                },
            ];
            if (this.canSeeAssignee) {
                fields.push({
                    key: 'assignee',
                    label: 'Assigned to',
                    sortable: true,
                });
            }
            return fields;
        },

        categories() {
            return [
                {
                    name: 'Search',
                    enabled: true,
                },
                {
                    name: 'Rubric',
                    enabled: true,
                },
                {
                    name: 'Hand-in instructions',
                    enabled: true,
                },
                {
                    name: 'Export',
                    enabled: this.canDownload,
                },
            ];
        },

        defaultCat() {
            if (!this.canSeeOthersWork && this.assignment.rubric != null) {
                return 'Rubric';
            } else if (!this.canSeeOthersWork && this.assignment.cgignore) {
                return 'Hand-in requirements';
            } else {
                return 'Search';
            }
        },

        exportFilename() {
            return this.assignment
                ? `${this.assignment.course.name}-${this.assignment.name}.csv`
                : null;
        },

        filteredSubmissions() {
            // WARNING: We need to access all, do not change!
            if (
                [
                    this.submissions,
                    this.latestOnly,
                    this.mineOnly,
                    this.userId,
                    this.filter,
                ].indexOf(undefined) !== -1
            ) {
                return [];
            }

            return filterSubmissions(
                this.submissions,
                this.latestOnly,
                this.mineOnly,
                this.userId,
                this.filter,
            ).map(sub => {
                if (sub.created_at > this.assignment.deadline) {
                    return Object.assign({}, sub, {
                        _rowVariant: 'danger',
                    });
                }
                return sub;
            });
        },

        manageAssignmentRoute() {
            return {
                name: 'manage_assignment',
                params: {
                    courseId: this.assignment.course.id,
                    assignmentId: this.assignment.id,
                },
            };
        },

        numStudents() {
            return new Set(this.submissions.map(sub => nameOfUser(sub.user))).size;
        },

        numFilteredStudents() {
            return new Set(this.filteredSubmissions.map(sub => nameOfUser(sub.user))).size;
        },
    },

    watch: {
        submissions(submissions) {
            this.latest = this.getLatest(submissions);
        },

        graders(graders) {
            if (graders == null) return;

            this.updateGraders(graders);
        },
    },

    mounted() {
        if (this.graders) {
            this.updateGraders(this.graders);
        }
        if (this.mineOnly == null) {
            this.mineOnly = this.submissions.some(
                s => s.user.id === this.userId || (s.assignee && s.assignee.id === this.userId),
            );
        }
        if (!this.mineOnly) {
            this.submit();
        }
    },

    methods: {
        ...mapActions('courses', ['forceLoadSubmissions']),

        submitForceLoadSubmissions() {
            return this.forceLoadSubmissions(this.assignment.id);
        },

        updateGraders(graders) {
            const assignees = graders.map(ass => ({
                value: ass.id,
                text: nameOfUser(ass),
                data: ass,
            }));
            assignees.unshift({ value: null, text: '-', data: null });
            this.assignees = assignees;
        },

        getLatest(submissions) {
            const latest = {};
            submissions.forEach(item => {
                if (!latest[item.user.id]) {
                    latest[item.user.id] = item.id;
                }
            });
            return latest;
        },

        sortChanged(context) {
            this.$router.replace({
                query: Object.assign({}, this.$route.query, {
                    sortBy: context.sortBy,
                    sortAsc: !context.sortDesc,
                }),
                hash: this.$route.hash,
            });
        },

        gotoSubmission(submission) {
            this.submit();

            this.$router.push({
                name: 'submission',
                params: { submissionId: submission.id },
                query: {
                    mine: this.mineOnly == null ? undefined : this.mineOnly,
                    latest: this.latestOnly == null ? undefined : this.latestOnly,
                    search: this.filter || undefined,
                    // Fuck you bootstrapVue (sortDesc should've been sortAsc)
                    sortBy: this.$refs.table.sortBy,
                    sortAsc: !this.$refs.table.sortDesc,
                    overview:
                        this.assignment.state === assignmentState.DONE && submission.grade != null,
                },
            });
        },

        submitDelayed() {
            if (this.submitTimeout != null) {
                clearTimeout(this.submitTimeout);
            }

            this.submitTimeout = setTimeout(() => {
                this.submitTimeout = null;
                this.submit();
            }, 200);
        },

        async submit() {
            await this.$nextTick();

            this.$router.replace({
                query: Object.assign({}, this.$route.query, {
                    latest: this.latestOnly,
                    mine: this.mineOnly,
                    q: this.filter || undefined,
                }),
                hash: this.$route.hash,
            });
        },

        updateAssignee(newId, { item: submission }) {
            const oldId = submission.assignee ? submission.assignee.id : null;
            if (oldId === newId) {
                return;
            }

            this.$set(this.assigneeUpdating, submission.id, true);

            let res;
            if (newId != null) {
                res = this.$http.patch(`/api/v1/submissions/${submission.id}/grader`, {
                    user_id: newId,
                });
            } else {
                res = this.$http.delete(`/api/v1/submissions/${submission.id}/grader`);
            }

            waitAtLeast(250, res).then(
                () => {
                    this.$set(this.assigneeUpdating, submission.id, false);
                    let newAssignee;
                    for (let i = 0; i < this.assignees.length; i += 1) {
                        if (this.assignees[i].data && this.assignees[i].data.id === newId) {
                            newAssignee = this.assignees[i].data;
                            break;
                        }
                    }
                    this.$emit('assigneeUpdated', submission, newAssignee);
                },
                ({ response }) => {
                    // TODO: visual feedback
                    // eslint-disable-next-line
                    console.log(response);
                },
            );
        },

        formatGrade,
        sortSubmissions,

        getHandedInLateText(sub) {
            const diff = moment(sub.created_at, moment.ISO_8601).from(
                moment(this.assignment.deadline, moment.ISO_8601),
                true, // Only get time string, not the 'in' before.
            );
            return `This submission was submitted ${diff} after the deadline.`;
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
        RubricEditor,
        SubmissionsExporter,
        LocalHeader,
        User,
        CategorySelector,
        CGIgnoreFile,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.separator.top-separator {
    margin: 0.5rem 0;
}

.separator.bottom-separator {
    margin-left: -1rem;
    margin-right: -1rem;
    margin-top: -1px;
}

.cat-container {
    margin: -1rem;
    padding: 1rem;
    background-color: white;

    #app.dark & {
        background-color: @color-primary;
    }
}

.empty-text {
    padding: 0.375rem 0.75rem;
    border: 1px solid transparent;
}

.submission-count {
    padding: 0.75rem;
    margin-bottom: 1rem;
    border: 1px solid #dee2e6;
    border-right-width: 0;
    border-left-width: 0;

    #app.dark & {
        border-color: @color-primary-darker;
    }
}

.late-icon {
    text-decoration: bold;
    margin-bottom: -0.125em;
    cursor: help;
}
</style>

<style lang="less">
@import '~mixins.less';

.submissions-table {
    margin-bottom: 0;

    td,
    th {
        vertical-align: middle;

        // student
        &:nth-child(1) {
            width: 30em;
        }

        // grade
        // created at
        // assignee
        &:nth-child(2),
        &:nth-child(3),
        &:nth-child(4) {
            width: 1px;
            white-space: nowrap;
        }

        .loader {
            padding: 0.33rem;
        }
    }
}

.submission-list .search-wrapper {
    #app.dark & .input-group-append .input-group-text {
        background-color: @color-primary-darkest !important;
    }
}
</style>
