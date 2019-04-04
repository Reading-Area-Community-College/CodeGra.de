<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader class="rubric-editor" v-if="loading"/>
<div v-else class="rubric-editor" :class="{ editable }">
    <b-tabs no-fade
            v-model="currentCategory">
        <b-nav-item slot="tabs" @click.prevent="appendRow" href="#"
                    v-if="editable">
            +
        </b-nav-item>

        <b-tab class="rubric"
               v-for="(rubric, i) in rubrics"
               :title="rubricCategoryTitle(rubric)"
               :key="`rubric-${rubric.id}-${i}`">

            <b-card no-block>
                <div class="card-header rubric-header">
                    <b-input-group style="margin-bottom: 1em;"
                                   v-if="editable">
                        <b-input-group-prepend is-text>
                            Category name
                        </b-input-group-prepend>
                        <input class="form-control"
                               placeholder="Category name"
                               @keydown.ctrl.enter="clickSubmit"
                               v-model="rubric.header"/>
                        <b-input-group-append>
                            <b-btn size="sm" variant="danger" class="float-right" @click="(e)=>deleteRow(i, e)">
                                Remove category
                            </b-btn>
                        </b-input-group-append>
                    </b-input-group>
                    <textarea class="form-control"
                              placeholder="Category description"
                              :tabindex="currentCategory === i ? null: -1"
                              v-model="rubric.description"
                              @keydown.ctrl.enter.prevent="clickSubmit"
                              v-if="editable"/>
                    <p v-else>{{ rubric.description }}</p>
                </div>
                <b-card-group class="rubric-items-container">
                    <b-card class="rubric-item"
                            v-for="(item, j) in rubric.items"
                            :key="`rubric-item-${item.id}-${j}-${i}`">
                        <b-input-group class="item-header-row">
                            <input v-if="editable"
                                   type="number"
                                   class="form-control item-points"
                                   step="any"
                                   :tabindex="currentCategory === i ? null: -1"
                                   placeholder="Points"
                                   @change="item.points = parseFloat(item.points)"
                                   @keydown="addItem(i, j)"
                                   @keydown.ctrl.enter="clickSubmit"
                                   v-model="item.points"/>
                            <span v-else
                                  class="item-points input disabled">
                                {{ item.points }}
                            </span>
                            <input type="text"
                                   v-if="editable"
                                   class="form-control item-header"
                                   placeholder="Header"
                                   :tabindex="currentCategory === i ? null: -1"
                                   @keydown="addItem(i, j)"
                                   @keydown.ctrl.enter="clickSubmit"
                                   v-model="item.header"/>
                            <span v-else class="input item-header disabled">
                                {{ item.header }}
                            </span>
                            <div class="item-info-button"
                                 v-if="rubric.items.length - 1 === j && editable"
                                 v-b-popover.top.hover="'Simply start typing to add a new item.'">
                                <icon name="info"/>
                            </div>
                            <div class="item-delete-button"
                                 v-else-if="editable"
                                 @click="deleteItem(i, j)">
                                <icon name="times"/>
                            </div>
                        </b-input-group>
                        <textarea v-model="item.description"
                                  class="item-description form-control"
                                  v-if="editable"
                                  :rows="8"
                                  :tabindex="currentCategory === i ? null: -1"
                                  @keydown="addItem(i, j)"
                                  @keydown.ctrl.enter.prevent="clickSubmit"
                                  placeholder="Description"/>
                        <p v-else
                           class="form-control input item-description disabled">
                            {{ item.description }}
                        </p>
                    </b-card>
                </b-card-group>
            </b-card>
        </b-tab>

        <div slot="empty" class="text-center text-muted empty" v-if="editable">
            <p>This assignment does not have rubric yet. Click the '+' to add a category.</p>
            <hr>

            <p>You can also import a rubric from a different assignment:</p>
            <b-alert v-if="loadAssignmentsFailed"
                     variant="danger"
                     class="assignment-alert"
                     show>
                Loading assignments failed.
            </b-alert>
            <b-input-group v-else>
                <multiselect
                    class="assignment-selector"
                    v-model="importAssignment"
                    :options="assignments || []"
                    :searchable="true"
                    :custom-label="a => `${a.course.name} - ${a.name}`"
                    :multiple="false"
                    track-by="id"
                    label="label"
                    :close-on-select="true"
                    :hide-selected="false"
                    placeholder="Select old assignment"
                    :internal-search="true"
                    :loading="loadingAssignments">
                    <span slot="noResult">
                        No results were found.
                    </span>
                </multiselect>
                <template slot="append">
                    <submit-button ref="importBtn"
                                   :disabled="!importAssignment"
                                   :submit="loadOldRubric"
                                   @after-success="afterLoadOldRubric"/>
                </template>
            </b-input-group>
        </div>

        <b-card class="extra-bar" v-if="!editable">
            <span>
                To get a full mark you need to score
                {{ internalFixedMaxPoints || curMaxPoints }} points in this
                rubric.
            </span>
            <slot/>
        </b-card>
    </b-tabs>

    <b-modal id="modal_delete_rubric" title="Are you sure?" :hide-footer="true">
        <p style="text-align: center;">
            By deleting a rubric the rubric and all grades given with it will be
            lost forever! So are you really sure?
        </p>
        <b-button-toolbar justify>
            <submit-button label="Yes"
                           variant="outline-danger"
                           :submit="deleteRubric"
                           :filter-error="deleteFilter"
                           @after-success="afterDeleteRubric"/>
            <b-btn class="text-center"
                   variant="success"
                   @click="$root.$emit('bv::hide::modal', 'modal_delete_rubric')">
                No!
            </b-btn>
        </b-button-toolbar>
    </b-modal>

    <div class="button-bar justify-content-center" v-if="editable">
        <b-alert v-if="showMaxPointsWarning"
                 variant="warning"
                 show>
            {{ maximumPointsWarningText }}
        </b-alert>
        <div class="override-checkbox">
            <b-input-group class="max-points-input-group">
                <b-input-group-prepend is-text>
                    Points needed for a 10:
                </b-input-group-prepend>
                <input type="number"
                       min="0"
                       step="1"
                       v-model="internalFixedMaxPoints"
                       class="form-control"
                       :placeholder="curMaxPoints"/>
                <b-input-group-append is-text>
                    out of {{ curMaxPoints }}
                    <description-popover
                        placement="top"
                        hug-text
                        description="The maximum amount of points a user can get
                                     for this rubric. You can set this to a
                                     higher or lower value manually, by default
                                     it is the sum of the max value in each
                                     category."/>
                </b-input-group-append>
            </b-input-group>
        </div>
    </div>

    <hr v-if="editable"/>

    <b-card class="button-bar" v-if="editable">
        <b-button-group class="danger-buttons">
            <b-button variant="danger"
                      v-b-popover.top.hover="'Delete rubric'"
                      @click="showDeleteModal"
                      :disabled="rubrics.length === 0">
                <icon name="times"/>
            </b-button>

            <submit-button variant="danger"
                           v-b-popover.top.hover="'Reset rubric'"
                           :submit="resetRubric"
                           confirm="Are you sure you want to revert your changes?"
                           :disabled="rubrics.length === 0">
                <icon name="reply"/>
            </submit-button>
        </b-button-group>

        <submit-button ref="submitButton" :submit="submit"/>
    </b-card>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';
import { mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/info';
import 'vue-awesome/icons/reply';
import arrayToSentence from 'array-to-sentence';

import { formatGrade } from '@/utils';

import SubmitButton from './SubmitButton';
import Loader from './Loader';
import DescriptionPopover from './DescriptionPopover';

export default {
    name: 'rubric-editor',
    data() {
        return {
            rubrics: [],
            selected: null,
            loading: true,
            currentCategory: 0,
            assignmentId: this.assignment.id,
            internalFixedMaxPoints: this.assignment.fixed_max_rubric_points,
            assignments: null,
            importAssignment: null,
            loadingAssignments: false,
            loadAssignmentsFailed: false,
        };
    },

    props: {
        assignment: {
            default: null,
        },

        editable: {
            type: Boolean,
            default: true,
        },

        fixedMaxPoints: {
            type: Number,
            default: null,
        },

        defaultRubric: {
            default: null,
        },

        hidden: {
            type: Boolean,
            default: false,
        },
    },

    watch: {
        assignmentId() {
            this.getAndSetRubrics();
        },

        hidden: {
            immediate: true,
            handler() {
                if (!this.hidden && this.assignments === null && this.rubrics.length === 0) {
                    this.loadAssignments();
                }
            },
        },
    },

    mounted() {
        if (this.defaultRubric) {
            this.setRubricData(this.defaultRubric);
            this.loading = false;
        } else {
            this.getAndSetRubrics().then(() => {
                this.loading = false;
            });
        }
    },

    computed: {
        maximumPointsWarningText() {
            const num = Number(this.internalFixedMaxPoints);
            if (num < this.curMaxPoints) {
                return `This means that a 10 will already be achieved with ${num} out of ${
                    this.curMaxPoints
                } rubric points.`;
            } else {
                return `This means that it will not be possible to achieve a 10, but a ${formatGrade(
                    this.curMaxPoints / num * 10,
                )} will be the maximum achievable grade.`;
            }
        },

        showMaxPointsWarning() {
            return (
                this.internalFixedMaxPoints !== '' &&
                this.internalFixedMaxPoints != null &&
                Number(this.internalFixedMaxPoints) !== this.curMaxPoints
            );
        },

        curMaxPoints() {
            return this.rubrics.reduce((cur, row) => {
                const extra = Math.max(
                    ...row.items.map(val => Number(val.points)).filter(item => !Number.isNaN(item)),
                );
                if (extra === -Infinity) {
                    return cur;
                }
                return cur + extra;
            }, 0);
        },
    },

    methods: {
        ...mapActions('courses', ['forceLoadSubmissions', 'forceLoadRubric', 'setRubric']),

        loadOldRubric() {
            return this.$http.post(`/api/v1/assignments/${this.assignmentId}/rubric`, {
                old_assignment_id: this.importAssignment.id,
            });
        },

        afterLoadOldRubric(response) {
            this.importAssignment = null;
            this.setRubricData(response.data);
        },

        loadAssignments() {
            this.loadingAssignments = true;
            this.assignments = [];
            this.$http.get('/api/v1/assignments/?only_with_rubric').then(
                ({ data }) => {
                    this.assignments = data;
                    this.loadingAssignments = false;
                },
                () => {
                    this.loadAssignmentsFailed = true;
                    this.loadingAssignments = false;
                },
            );
        },

        getEmptyItem() {
            return {
                points: '',
                header: '',
                description: '',
            };
        },

        resetFixedMaxPoints() {
            this.internalFixedMaxPoints = null;
            this.ensureFixedMaxPoints();

            return this.$http.put(`/api/v1/assignments/${this.assignmentId}/rubrics/`, {
                max_points: this.internalFixedMaxPoints,
            });
        },

        afterResetFixedMaxPoints(response) {
            this.setRubric({
                assignmentId: this.assignmentId,
                rubric: response.data,
                maxPoints: this.internalFixedMaxPoints,
            });
        },

        getEmptyRow() {
            return {
                header: '',
                description: '',
                items: [this.getEmptyItem()],
            };
        },

        resetRubric() {
            this.loading = true;
            return this.getAndSetRubrics().then(
                () => {
                    this.loading = false;
                },
                err => {
                    this.loading = false;
                    throw err;
                },
            );
        },

        setRubricData(serverRubrics) {
            this.rubrics = serverRubrics.map(origRow => {
                const row = Object.assign({}, origRow);

                // We map and `Object.assign` here so we have a complete new
                // object to sort.
                row.items = row.items
                    .map(item => Object.assign({}, item))
                    .sort((a, b) => a.points - b.points);
                if (this.editable) {
                    row.items.push(this.getEmptyItem());
                }

                return row;
            });
        },

        async getAndSetRubrics() {
            if (!this.assignmentId) return;

            await this.forceLoadRubric(this.assignmentId);
            if (this.assignment && this.assignment.rubric) {
                this.setRubricData(this.assignment.rubric);
            } else {
                this.rubrics = [];
            }
        },

        createRow() {
            this.rubrics.push(this.getEmptyRow());
        },

        showDeleteModal() {
            this.$root.$emit('bv::show::modal', 'modal_delete_rubric');
        },

        deleteRubric() {
            return this.$http.delete(`/api/v1/assignments/${this.assignmentId}/rubrics/`);
        },

        deleteFilter(err) {
            if (err.response && err.response.status === 404) {
                return err;
            } else {
                throw err;
            }
        },

        afterDeleteRubric() {
            this.loadAssignments();
            this.rubrics = [];

            this.$root.$emit('bv::hide::modal', 'modal_delete_rubric');

            this.setRubric({
                assignmentId: this.assignmentId,
                rubric: null,
                maxPoints: null,
            });
        },

        ensureFixedMaxPoints() {
            if (this.internalFixedMaxPoints === '' || this.internalFixedMaxPoints == null) {
                this.internalFixedMaxPoints = null;
            } else if (Number.isNaN(Number(this.internalFixedMaxPoints))) {
                throw new Error(
                    `The given max points "${this.internalFixedMaxPoints}" is not a number`,
                );
            } else {
                this.internalFixedMaxPoints = Number(this.internalFixedMaxPoints);
            }
        },

        getCheckedRubricRows() {
            const wrongCategories = [];
            const wrongItems = [];
            let hasUnnamedCategories = false;

            const rows = [];
            for (let i = 0, len = this.rubrics.length; i < len; i += 1) {
                const row = this.rubrics[i];

                const res = {
                    header: row.header,
                    description: row.description,
                    items: [],
                };

                if (res.header.length === 0) {
                    hasUnnamedCategories = true;
                }

                for (let j = 0, len2 = row.items.length - 1; j < len2; j += 1) {
                    if (Number.isNaN(parseFloat(row.items[j].points))) {
                        wrongItems.push(
                            `'${row.header || '[No name]'} - ${row.items[j].header ||
                                '[No name]'}'`,
                        );
                    }
                    row.items[j].points = parseFloat(row.items[j].points);

                    res.items.push(row.items[j]);
                }

                if (res.items.length === 0) {
                    wrongCategories.push(row.header || '[No name]');
                }

                if (row.id !== undefined) res.id = row.id;

                rows.push(res);
            }

            if (hasUnnamedCategories) {
                throw new Error('There are unnamed categories!');
            }

            if (wrongItems.length > 0) {
                const multiple = wrongItems.length > 2;
                throw new Error(`
For the following item${multiple ? 's' : ''} please make sure "points" is
a number: ${arrayToSentence(wrongItems)}.`);
            }

            if (wrongCategories.length > 0) {
                const multiple = wrongCategories.length > 2;
                throw new Error(`
The following categor${multiple ? 'ies have' : 'y has'} a no items:
${arrayToSentence(wrongCategories)}.`);
            }

            if (rows.length === 0) {
                throw new Error('You cannot submit an empty rubric.');
            }

            return rows;
        },

        clickSubmit() {
            this.$refs.submitButton.onClick();
        },

        submit() {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            const rows = this.getCheckedRubricRows();
            this.ensureFixedMaxPoints();

            return this.$http.put(`/api/v1/assignments/${this.assignmentId}/rubrics/`, {
                rows,
                max_points: this.internalFixedMaxPoints,
            });
        },

        afterSubmit(response) {
            this.setRubricData(response.data);
            this.setRubric({
                assignmentId: this.assignmentId,
                rubric: response.data,
                maxPoints: this.internalFixedMaxPoints,
            });
            this.forceLoadSubmissions(this.assignmentId);
        },

        addRubricRow() {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            this.$set(this.rubrics, this.rubrics.length, {
                header: '',
                description: '',
                items: [this.getEmptyItem()],
            });
        },

        addItem(i, j) {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            if (this.rubrics[i].items.length - 1 === j) {
                this.$set(this.rubrics[i].items, j + 1, this.getEmptyItem());
            }
        },

        deleteItem(i, j) {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            this.rubrics[i].items.splice(j, 1);
        },

        appendRow() {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            this.rubrics.push(this.getEmptyRow());
            this.$nextTick(() => {
                this.currentCategory = this.rubrics.length - 1;
            });
        },

        deleteRow(i, e) {
            if (!this.editable) {
                throw Error('This rubric editor is not editable.');
            }

            this.rubrics.splice(i, 1);
            e.preventDefault();
            e.stopPropagation();
        },

        rubricCategoryTitle(category) {
            return category.header || '<span class="unnamed">Unnamed category</span>';
        },
    },

    components: {
        Icon,
        SubmitButton,
        Loader,
        DescriptionPopover,
        Multiselect,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

@rubric-items-per-row: 4;
@rubric-items-fixed-offset: @rubric-items-per-row + 1;
@rubric-item-min-width: 100% / @rubric-items-per-row;

.rubric-editor {
    margin-bottom: 0;

    .card.rubric-item {
        min-width: @rubric-item-min-width;
        padding: 0.5rem;
        border-bottom: 0;
        border-top: 0;
        border-left: 0;
        border-radius: 0;

        &:nth-child(n + @{rubric-items-fixed-offset}) {
            flex: 0 0 @rubric-item-min-width;
        }

        &:last-child {
            border-right: 0;
        }
    }

    .rubric-items-container {
        border-bottom: 0;
    }

    .rubric-header {
        padding: 0 !important;
        margin-bottom: 1em;
        .default-background;
        p {
            font-size: 1.1rem;
            line-height: 1.25;
            .default-text-colors;
            min-height: 2em;
        }
        border-bottom: 0;
        input:focus {
            background: #f7f7f9;
        }
    }

    .card,
    card-header {
        border-radius: 0;
        &:not(.tab) {
            border-bottom: 0 !important;
            border-right: 0 !important;
        }
        border-top: 0 !important;
        border-left: 0 !important;
    }

    .rubric-editor {
        .card-header,
        .card-block {
            padding: 0.5rem 0.75rem;
            .rubric-item-wrapper {
                margin: -0.5em;
                padding: 0.5em;
                align-items: center;
            }
        }
    }

    .rubric {
        flex: 1 1 0;
        min-width: 100%;
        background-color: white;
        padding: 1em;
        border: 1px solid transparent !important;

        #app.dark & {
            background-color: @color-primary;
        }

        .item-description {
            background-color: @color-lightest-gray;
        }

        .input.disabled {
            #app.dark & {
                color: @text-color-dark !important;
            }

            &.item-description {
                height: 10em;
                overflow: auto;
            }
        }

        .rubric-items-container input,
        .rubric-items-container span.input {
            font-weight: bold;
            background: transparent;

            border: 1px solid transparent !important;
            margin-bottom: 0.2em;

            &:hover:not(.disabled) {
                border-bottom: 1px solid @color-primary-darkest !important;
            }

            &:focus:not(.disabled) {
                border-color: #5cb3fd !important;
                cursor: text;
            }

            &.item-points,
            &.item-header {
                min-width: 0;
                padding: 0.375rem 0.1rem;
            }

            &.item-points {
                flex: 0 0 4rem;
                margin-right: 0.2rem;
                text-align: left;

                &:not(:focus) {
                    border-radius: 0;
                }

                &.disabled {
                    flex-basis: auto;
                    padding-left: 10px;
                }
            }

            &.item-header {
                flex: 1 1 auto;
                margin-left: 0.1rem;

                &:focus {
                    border-top-right-radius: 0.25rem;
                    border-bottom-right-radius: 0.25rem;
                }
            }
        }
    }

    &:not(.editable) .rubric {
        padding-bottom: 0;
    }

    .item-delete-button,
    .item-info-button {
        color: @color-border-gray;
        padding: 0.5rem;
    }

    .item-delete-button:hover {
        .default-text-colors;
        cursor: pointer;
    }

    .item-info-button:hover {
        .default-text-colors;
        cursor: help;
    }
}

.empty {
    padding: 2em;
}

.button-bar,
.card.extra-bar {
    border: 0;

    .card-body {
        justify-content: space-between;
        display: flex;
        flex-direction: row;
        align-items: center;
    }
}

.button-bar {
    margin-top: 1.25rem;

    .override-checkbox {
        justify-content: center;
        display: flex;
        flex: 0 1 auto;
        flex-direction: column;
        align-items: center;

        .max-points-input-group {
            width: auto;
        }
    }

    input {
        width: 5em;
    }
}

.card.extra-bar {
    padding: 0 1rem 1rem 1.5rem;
}

.card-body {
    padding: 0;
}

.danger-buttons {
    .btn {
        width: 50%;
    }

    .btn:first-child {
        border-right: 1px solid white;
    }

    .btn:last-child {
        border-left: 1px solid white;
    }

    #app.dark & .btn {
        border-color: @color-primary;
    }
}

.assignment-alert.alert {
    margin-bottom: 0;
}
</style>

<style lang="less">
@import '~mixins.less';

.rubric-editor {
    &:not(.editable) {
        .nav-tabs {
            .nav-item:first-child {
                margin-left: 15px;
            }
            .nav-link:hover {
                border-color: @color-light-gray;
            }
        }
    }
    .rubric-items-container .card.rubric-item > .card-block {
        border: 0;
    }

    .nav-tabs {
        .nav-link {
            border-bottom: 0;

            .unnamed {
                color: @color-light-gray;
            }
        }
    }

    .tab-content {
        #app.dark & {
            border-color: @color-primary-darker;
        }
        border: 1px solid #dee2e6;
        border-top: 0;
        border-bottom-right-radius: 0.25rem;
        border-bottom-left-radius: 0.25rem;
    }

    .assignment-selector {
        z-index: 8;
        flex: 1;
        .multiselect__tags {
            border-bottom-right-radius: 0;
            border-top-right-radius: 0;
        }
    }
}
</style>
