<template>
<div class="plagiarism-runner">
    <loader :scale="2" v-if="(canView || canManage) && runs == null"/>
    <table v-else-if="(canView || canManage) && runs.length"
           class="table table-striped runs-table">
        <thead>
            <tr>
                <th>Previous runs</th>
                <th :colspan="canManage ? 2 : 1">State</th>
            </tr>
        </thead>

        <tbody>
            <tr v-for="run, i in runs"
                :class="{ [`run-${run.state}`]: canView }"
                @click="goToOverview(run)">
                <td>
                    <a v-if="canGoToOverview(run)"
                        class="invisible-link"
                        href="#"
                        @click.prevent>
                        {{ run.provider_name }}
                    </a>
                    <span v-else>
                        {{ run.provider_name }}
                    </span>
                </td>
                <td class="run-state">
                    {{ run.state }}
                </td>
                <td v-if="canManage"
                    class="run-delete">
                    <submit-button default="danger"
                                   size="sm"
                                   :label="false"
                                   confirm="Are you sure you want to delete
                                            the results?"
                                   @click="deleteRun(run, i)"
                                   @click.native.stop
                                   v-b-popover.hover.top="'Delete results'"
                                   ref="deleteRunButton">
                        <icon name="times"/>
                    </submit-button>
                </td>
            </tr>
        </tbody>
    </table>

    <loader :scale="2" v-if="canManage && providers == null"/>
    <div v-else-if="canManage">
        <b-form-radio-group v-model="selectedProvider">
            <table class="table table-striped table-hover providers-table">
                <thead>
                    <tr>
                        <th>New run</th>
                    </tr>
                </thead>

                <tbody>
                    <tr v-for="provider in providers"
                        @click="selectedProvider = provider">
                        <td>
                            <b-form-radio :value="provider">
                                {{ provider.name }}
                            </b-form-radio>
                        </td>
                    </tr>
                </tbody>
            </table>
        </b-form-radio-group>

        <div v-if="selectedProvider != null">
            <table class="table table-striped options-table">
                <thead>
                    <tr>
                        <th>Option</th>
                        <th>Value</th>
                    </tr>
                </thead>

                <tbody>
                    <tr v-for="option in selectedProvider.options">
                        <td>
                            {{ option.title }}
                            <sup v-if="option.mandatory"
                                 v-b-popover.hover.top="'This option is required'"
                                 class="description">
                                *
                            </sup>
                            <description-popover hug-text
                                                 :description="option.description"/>
                        </td>
                        <td>
                            <input v-if="option.type == 'strvalue'"
                                   type="text"
                                   class="form-control"
                                   @keydown.ctrl.enter="runPlagiarismChecker"
                                   :placeholder="option.placeholder"
                                   v-model="selectedOptions[option.name]"/>
                            <input v-else-if="option.type == 'numbervalue'"
                                   @input="selectedOptions[option.name] = $event.target.value == '' ? undefined : (
                                           isNaN(Number($event.target.value)) ? ($event.target.value)
                                                                              : Number($event.target.value))"
                                   type="number"
                                   class="form-control"
                                   :placeholder="option.placeholder"
                                   @keydown.ctrl.enter="runPlagiarismChecker"/>
                            <b-form-checkbox v-else-if="option.type == 'boolvalue'"
                                             v-model="selectedOptions[option.name]"/>
                            <b-form-select v-else-if="option.type == 'singleselect'"
                                           :options="option.possible_options"
                                           v-model="selectedOptions[option.name]"/>
                            <multiselect v-else-if="option.type == 'multiselect'"
                                         v-model="selectedOptions[option.name]"
                                         :options="option.possible_options"
                                         :searchable="true"
                                         :multiple="true"
                                         track-by="id"
                                         label="label"
                                         :close-on-select="false"
                                         select-label=""
                                         :hide-selected="true"
                                         :internal-search="true"
                                         :loading="option.possible_options === 0">
                                <span slot="noResult">
                                    No results were found.
                                </span>
                            </multiselect>
                        </td>
                    </tr>
                </tbody>
            </table>

            <submit-button label="Run"
                           id="plagiarism-run-button"
                           class="run-button"
                           ref="runButton"
                           :disabled="!allOptionsValid"
                           @click="runPlagiarismChecker"
                           @mouseenter.native="!allOptionsValid && $refs.runButtonPopover.$emit('open')"
                           @mouseleave.native="!allOptionsValid && $refs.runButtonPopover.$emit('close')"/>
            <b-popover target="plagiarism-run-button"
                       content="Not all mandatory options have been set!"
                       placement="left"
                       ref="runButtonPopover"
                       v-if="!allOptionsValid"/>
        </div>
    </div>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';

import { cmpNoCase } from '@/utils';

import DescriptionPopover from './DescriptionPopover';
import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'plagiarism-runner',

    props: {
        assignment: {
            type: Object,
            required: true,
        },

        canManage: {
            type: Boolean,
            required: true,
        },

        canView: {
            type: Boolean,
            required: true,
        },
    },

    data() {
        return {
            providers: null,
            selectedProvider: null,
            selectedOptionsMap: new WeakMap(),
            selectedOptions: null,
            allOldAssignments: [],
            runs: null,
            runsPollingInterval: null,
        };
    },

    computed: {
        course() {
            return this.assignment.course;
        },

        allOptionsValid() {
            return this.selectedProvider.options.every(option => this.isValid(option));
        },

        oldAssignments() {
            return this.allOldAssignments.filter(
                assig => assig.id !== this.assignment.id,
            );
        },
    },

    watch: {
        selectedProvider(provider) {
            if (provider == null) {
                return;
            }

            if (this.selectedOptionsMap.get(provider) == null) {
                this.selectedOptionsMap.set(provider, this.makeOptions(provider));
            }

            this.selectedOptions = this.selectedOptionsMap.get(provider);

            if (this.allOldAssignments.length === 0) {
                this.getOldAssignments();
            }
        },

        $route(oldRoute, newRoute) {
            if (oldRoute.params.assignmentId !== newRoute.params.assignmentId) {
                this.selectedProvider = null;
                this.loadRuns();
            }
        },
    },

    methods: {
        makeOptions(provider) {
            const options = { provider: provider.name };

            for (let i = 0, l = provider.options.length; i < l; i++) {
                options[provider.options[i].name] = undefined;
            }

            return options;
        },

        isValid(option) {
            return !option.mandatory || this.selectedOptions[option.name];
        },

        setOption(option, value) {
            this.selectedOptions = Object.assign({}, this.selectedOptions, {
                [option.name]: value,
            });
        },

        async runPlagiarismChecker() {
            const selectedOptions = Object.assign({}, this.selectedOptions);

            if (this.selectedOptions.old_assignments == null) {
                selectedOptions.old_assignments = [];
            } else {
                selectedOptions.old_assignments = this.selectedOptions.old_assignments.map(
                    assig => assig.id,
                );
            }

            const req = this.$http.post(
                `/api/v1/assignments/${this.assignment.id}/plagiarism`,
                selectedOptions,
            ).then(
                (res) => {
                    this.runs.push(res.data);
                },
                (err) => {
                    let res = err.response.data.message;
                    if (err.response.data.invalid_options) {
                        res += ` (${err.response.data.invalid_options.join('. ')})`;
                    }
                    throw res;
                },
            );

            this.$refs.runButton.submit(req);
        },

        async getOldAssignments() {
            const permissions = Object.entries(await this.$http.get(
                '/api/v1/permissions/?type=course&permission=can_view_plagiarism',
            ).then(
                ({ data }) => data,
                () => {},
            ));

            const assignments = (await Promise.all(permissions.reduce(
                (promises, [courseId, { can_view_plagiarism: canView }]) => {
                    if (canView) {
                        promises.push(
                            this.$http.get(`/api/v1/courses/${courseId}/assignments/`).then(
                                ({ data }) => data,
                                () => [],
                            ),
                        );
                    }
                    return promises;
                },
                [],
            ))).reduce(
                (a, b) => a.concat(b),
            ).map(
                (assig) => {
                    const courseName = this.$htmlEscape(assig.course.name);
                    const assigName = this.$htmlEscape(assig.name);
                    assig.label = `${courseName} - ${assigName}`;
                    return assig;
                },
            ).sort(
                (a, b) => cmpNoCase(a.label, b.label),
            );

            if (assignments.length) {
                this.allOldAssignments.push(...assignments);
                this.addOldAssignmentsOption();
            }
        },

        addOldAssignmentsOption() {
            for (let i = 0, l = this.providers.length; i < l; i++) {
                this.providers[i].options.push({
                    name: 'old_assignments',
                    title: 'Old assignments',
                    description: 'Include submissions from assignments from previous years in this run.',
                    type: 'multiselect',
                    mandatory: false,
                    possible_options: this.oldAssignments,
                });
            }
        },

        canGoToOverview(run) {
            return this.canView && run.state === 'done';
        },

        goToOverview(run) {
            if (!this.canGoToOverview(run)) {
                return;
            }

            this.$router.push({
                name: 'plagiarism_overview',
                params: {
                    courseId: this.course.id,
                    assignmentId: this.assignment.id,
                    plagiarismRunId: run.id,
                },
            });
        },

        async loadProviders() {
            if (!this.canManage) {
                this.providers = [];
                return;
            }

            const { data: providers } = await this.$http.get('/api/v1/plagiarism/').catch(
                () => [],
            );
            this.providers = providers;
        },

        async loadRuns() {
            if (!(this.canView || this.canManage)) {
                this.runs = [];
                return;
            }

            const { data: runs } = await this.$http.get(
                `/api/v1/assignments/${this.assignment.id}/plagiarism/`,
            ).catch(
                () => [],
            );
            this.runs = runs;
        },

        pollRuns() {
            this.runsPollingInterval = setInterval(() => {
                const running = this.runs.filter(
                    run => run.state === 'running',
                );

                if (!running.length) {
                    return;
                }

                this.loadRuns();
            }, 5000);
        },

        deleteRun(run, i) {
            this.$refs.deleteRunButton[i].submit(
                this.$http.delete(`/api/v1/plagiarism/${run.id}`).catch(
                    ({ response }) => {
                        throw response.data.message;
                    },
                ),
            ).then(
                () => {
                    this.runs.splice(i, 1);
                },
                () => {},
            );
        },
    },

    async mounted() {
        await Promise.all([this.loadProviders(), this.loadRuns()]);

        this.pollRuns();
    },

    destroyed() {
        clearInterval(this.runsPollingInterval);
    },

    components: {
        DescriptionPopover,
        Icon,
        Loader,
        Multiselect,
        SubmitButton,
    },
};
</script>

<style lang="less">
@import "~mixins.less";

.plagiarism-runner > .loader {
    margin: 1rem;
}

.runs-table {
    &:last-child {
        margin-bottom: 0;
    }

    tr.run-done:hover {
        background-color: rgba(0, 0, 0, .075);
        cursor: pointer;
    }

    td {
        vertical-align: middle;
    }

    .run-state {
        text-transform: capitalize;
    }

    .run-delete {
        width: 1px;
        white-space: nowrap;
    }
}

.providers-table {
    margin: 0;
}

.options-table {
    border-bottom: 1px solid rgba(0, 0, 0, .15);
    cursor: default !important;

    #app.dark & {
        border-bottom: 1px solid @color-primary-darkest;
    }

    td {
        vertical-align: middle;
    }

    td:first-child {
        width: 1px;
        white-space: nowrap;
    }
}

.run-button {
    float: right;
    margin-right: 1rem;
}
</style>
