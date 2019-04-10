<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="divide-submissions">
    <table class="table table-striped grader-list">
        <thead>
            <tr>
                <th class="name">Grader</th>
                <th class="weight">Weight</th>
                <th class="percentage">Percent</th>
            </tr>
        </thead>

        <tbody :class="{ 'disabled-table': tableDisabled }"
               v-b-popover.top.hover="textDisabledPopover">
            <tr v-for="grader, i in graders"
                :class="{ 'text-muted': tableDisabled }"
                class="grader">
                <td class="name">
                    <b-form-checkbox @change="graderChanged(i)"
                                     :disabled="tableDisabled"
                                     :checked="grader.weight != 0">
                        <user :user="grader"/>
                    </b-form-checkbox>
                </td>
                <td class="weight">
                    <input class="form-control"
                           :class="{ 'text-muted': tableDisabled }"
                           :disabled="tableDisabled"
                           type="number"
                           min="0"
                           step="1"
                           ref="inputField"
                           style="min-width: 3em;"
                           @keydown.ctrl.enter="$refs.submitButton.onClick"
                           v-model.number="grader.weight"/>
                </td>
                <td class="percentage">
                    {{ (100 * grader.weight / totalWeight).toFixed(1) }}%
                </td>
            </tr>
        </tbody>
    </table>

    <b-button-toolbar v-if="graders.length"
                      justify
                      class="button-bar">
        <multiselect class="assignment-selector"
                     :disabled="divisionChildren.length > 0"
                     v-model="importAssignment"
                     :options="otherAssignments"
                     :searchable="true"
                     :multiple="false"
                     track-by="id"
                     label="name"
                     placeholder="Connect divisions to"
                     :close-on-select="true"
                     :hide-selected="false"
                     :internal-search="true"
                     :loading="false">
            <template slot="option" slot-scope="prop">
                <span :class="{ 'disabled-option': getDivisionParent(prop.option) }">
                    {{ prop.option.name }}
                </span>
            </template>
            <span slot="noResult">
                No results were found.
            </span>
        </multiselect>
        <div id="division-submit-button-wrapper">
            <submit-button label="Divide"
                           :disabled="divisionChildren.length > 0 || invalidParentSelected"
                           style="height: inherit;"
                           :submit="divideSubmissions"
                           @success="afterDivideSubmissions"
                           ref="submitButton"/>
        </div>
        <b-popover triggers="click hover"
                   show
                   v-if="invalidParentSelected"
                   target="division-submit-button-wrapper">
            <div style="text-align: justify;">
                The division of the selected assignment is determined by
                {{getDivisionParent(importAssignment).name}}, so you cannot
                connect to this assignment.
            </div>
        </b-popover>
    </b-button-toolbar>
    <span v-else>No graders found for this assignment</span>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import Multiselect from 'vue-multiselect';

import Loader from './Loader';
import SubmitButton from './SubmitButton';
import User from './User';

export default {
    name: 'divide-submissions',

    props: {
        assignment: {
            type: Object,
            default: null,
        },

        graders: {
            type: Array,
            default: null,
        },
    },

    data() {
        return {
            importAssignment: null,
        };
    },

    watch: {
        currentDivisionParent(newVal) {
            if (newVal != null && this.importAssignment != null) {
                this.importAssignment = {
                    id: newVal.id,
                    name: newVal.name,
                };
            }
        },
    },

    mounted() {
        if (this.currentDivisionParent) {
            const a = this.currentDivisionParent;
            this.importAssignment = { id: a.id, name: a.name };
        }
    },

    computed: {
        ...mapGetters('courses', ['courses', 'assignments']),

        currentDivisionParent() {
            return this.assignments[this.assignment.division_parent_id];
        },

        textDisabledPopover() {
            if (this.divisionChildren.length > 0) {
                const other = this.divisionChildren.map(a => a.name).join(', ');
                return `The graders of ${other} are connected to this assignment. This means you cannot change the division of this assignment.`;
            } else if (
                this.importAssignment &&
                this.currentDivisionParent &&
                this.currentDivisionParent.id === this.importAssignment.id
            ) {
                return `These values are determined by ${this.importAssignment.name}.`;
            } else if (this.importAssignment) {
                return `These values will be determined by ${
                    this.importAssignment.name
                } when you connect to it.`;
            } else {
                return '';
            }
        },

        invalidParentSelected() {
            return this.importAssignment && !!this.getDivisionParent(this.importAssignment);
        },

        divisionChildren() {
            return this.courses[this.assignment.course.id].assignments
                .filter(a => a.division_parent_id === this.assignment.id)
                .map(a => ({ id: a.id, name: a.name }));
        },

        tableDisabled() {
            return this.divisionChildren.length > 0 || !!this.importAssignment;
        },

        totalWeight() {
            const graderWeight = this.graders.reduce(
                (tot, grader) => tot + (grader.weight || 0),
                0,
            );
            return Math.max(graderWeight, 1);
        },

        otherAssignments() {
            return this.courses[this.assignment.course.id].assignments
                .filter(
                    a => a.id !== this.assignment.id,
                    // This map is needed as a recursion error occurs otherwise
                )
                .map(a => ({
                    id: a.id,
                    name: a.name,
                }));
        },
    },

    methods: {
        ...mapActions('courses', ['forceLoadSubmissions', 'updateAssignment']),

        getDivisionParent(assig) {
            return this.assignments[this.assignments[assig.id].division_parent_id];
        },

        graderChanged(i) {
            this.graders[i].weight = this.graders[i].weight ? 0 : 1;
            const field = this.$refs.inputField[i];
            field.focus();
        },

        divideSubmissions() {
            if (this.importAssignment) {
                return this.$http.patch(
                    `/api/v1/assignments/${this.assignment.id}/division_parent`,
                    {
                        parent_id: this.importAssignment.id,
                    },
                );
            } else {
                const negativeWeights = Object.values(this.graders)
                    .filter(x => x.weight < 0);

                if (negativeWeights.length) {
                    const names = negativeWeights.map(x => x.name).join(', ');
                    const multi = negativeWeights.length > 1;
                    throw new Error(
                        `Negative weights are not allowed, but the
                        weight${multi ? 's' : ''} for ${names}
                        ${multi ? 'are' : 'is'} negative.`,
                    );
                }

                let req = Promise.resolve();
                if (this.currentDivisionParent != null) {
                    req = req.then(() =>
                        this.$http.patch(
                            `/api/v1/assignments/${this.assignment.id}/division_parent`,
                            {
                                parent_id: null,
                            },
                        ),
                    );
                }

                return req.then(() =>
                    this.$http.patch(`/api/v1/assignments/${this.assignment.id}/divide`, {
                        graders: Object.values(this.graders)
                            .filter(x => x.weight !== 0)
                            .reduce((res, g) => {
                                res[`${g.id}`] = g.weight;
                                return res;
                            }, {}),
                    }),
                );
            }
        },

        afterDivideSubmissions() {
            this.updateAssignment({
                assignmentId: this.assignment.id,
                assignmentProps: {
                    division_parent_id: this.importAssignment && this.importAssignment.id,
                },
            });
            this.forceLoadSubmissions(this.assignment.id);
            this.$emit('divided');
        },
    },

    components: {
        Loader,
        SubmitButton,
        User,
        Multiselect,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.grader-list,
.divide-submissions {
    margin-bottom: 1rem;
}

th {
    border-top: 0;
}

.grader {
    border-bottom: 1px solid #dee2e6;

    #app.dark & {
        border-bottom: 1px solid @color-primary-darker;
    }
}

.disabled-table {
    cursor: not-allowed;
}

tbody .weight {
    padding: 0;

    input {
        padding: 0.75rem;
        border: none;
        border-bottom: 1px solid transparent !important;
        border-radius: 0;
        background: transparent !important;

        &:not(:disabled):hover {
            border-color: @color-primary !important;

            #app.dark & {
                border-color: @color-primary-darkest !important;
            }
        }
    }
}

.weight,
.percentage {
    text-align: right;
}

.name,
.percentage {
    width: 1px;
    white-space: nowrap;
}

.button-bar {
    margin: 0 1rem;
    .assignment-selector {
        flex: 0 1 70%;
    }
    .submit-button {
        flex: 0;
    }
}
</style>

<style lang="less">
.divide-submissions {
    .grader-list {
        .custom-checkbox {
            display: flex;

            label {
                width: 100%;
            }
        }
    }

    .disabled-option {
        font-style: italic !important;
    }

    .multiselect__option:not(.multiselect__option--highlight) {
        .disabled-option {
            color: #cecece;
        }
    }
}
</style>
