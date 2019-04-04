<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="plagiarism-runner">
    <loader :scale="2" v-if="runs == null || providers == null"/>
    <div v-else>
        <table v-if="(canView || canManage) && runs.length"
               class="table table-striped runs-table">
            <thead>
                <tr>
                    <th>Previous runs</th>
                    <th>Started</th>
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
                        <description-popover hug-text>
                            <div slot="description" class="selected-options-popover">
                                Selected options:
                                <ul>
                                    <li v-for="config in run.config">
                                        {{ translateOption(config[0], run) }}: {{ config[1] }}
                                    </li>
                                </ul>
                            </div>
                        </description-popover>
                    </td>
                    <td>
                        {{ run.formatted_created_at }}
                    </td>
                    <td>
                        <div v-if="showProgress(run)">
                            <b-progress v-model="run.submissions_done"
                                        :max="run.submissions_total"
                                        :precision="1"
                                        animated/>
                            <span class="text-center progress-text">
                                <span class="run-state">{{ run.state }}</span>
                                {{ run.submissions_done }} out of {{ run.submissions_total }}
                            </span>
                        </div>
                        <span class="run-state" v-else>
                            {{ run.state }}
                            <loader v-if="!runIsFinished(run)"
                                    :scale="1"
                                    v-b-popover.hover.top="'This job is running'"/>
                        </span>
                    </td>
                    <td class="run-delete">
                        <submit-button v-if="canManage"
                                       :variant="runIsFinished(run) ? 'danger' : 'warning'"
                                       size="sm"
                                       :confirm="runIsFinished(run) ? 'Are you sure you want to delete the results?'
                                                : 'Are you sure you want to cancel this run?'"
                                       :submit="() => deleteRun(run)"
                                       @after-success="afterDeleteRun(run)"
                                       @click.native.stop
                                       v-b-popover.hover.top="runIsFinished(run) ? 'Delete results' : 'Cancel run'">
                            <icon name="times"/>
                        </submit-button>
                    </td>
                </tr>
            </tbody>
        </table>

        <div v-if="canManage">
            <b-form-radio-group v-model="selectedProvider"
                                v-if="providers.length > 1"
                                class="provider-selectors">
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
                                       @keydown.ctrl.enter="$refs.runButton.onClick"
                                       :placeholder="option.placeholder"
                                       v-model="selectedOptions[option.name]"/>
                                <input v-else-if="option.type == 'numbervalue'"
                                       @input="selectedOptions[option.name] = $event.target.value == '' ? undefined : (
                                           isNaN(Number($event.target.value)) ? ($event.target.value)
                                           : Number($event.target.value))"
                                       type="number"
                                       class="form-control"
                                       :placeholder="option.placeholder"
                                       @keydown.ctrl.enter="$refs.runButton.onClick"/>
                                <b-form-checkbox v-else-if="option.type == 'boolvalue'"
                                                 v-model="selectedOptions[option.name]"/>
                                <b-form-select v-else-if="option.type == 'singleselect'"
                                               :options="option.possible_options"
                                               v-model="selectedOptions[option.name]"/>
                                <multiselect v-else-if="option.type == 'multiselect'"
                                             v-model="selectedOptions[option.name]"
                                             :options="option.possible_options || []"
                                             :searchable="true"
                                             :multiple="true"
                                             track-by="id"
                                             label="label"
                                             :close-on-select="false"
                                             select-label=""
                                             :hide-selected="true"
                                             :internal-search="true"
                                             :loading="option.possible_options == null">
                                    <span slot="noResult">
                                        No results were found.
                                    </span>
                                </multiselect>
                                <div v-else-if="option.type === 'file'" style="display: flex;">
                                    <b-form-file :class="`file-uploader-form ${option.name}`"
                                                 :ref="`${selectedProvider.name}||${option.name}`"
                                                 name="file"
                                                 style="z-index: 0;"
                                                 placeholder="Click here to choose a file..."
                                                 v-model="selectedOptions[option.name]"/>
                                    <b-btn variant="warning"
                                           style="margin-left: 5px;"
                                           @click="$refs[`${selectedProvider.name}||${option.name}`].map(a => a.reset())">Clear</b-btn>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>

                <submit-button id="plagiarism-run-button"
                               class="run-button"
                               ref="runButton"
                               label="Run"
                               :disabled="!allOptionsValid"
                               :submit="runPlagiarismChecker"
                               @success="afterRunPlagiarismChecker"
                               @mouseenter.native="!allOptionsValid && $refs.runButtonPopover.$emit('open')"
                               @mouseleave.native="!allOptionsValid && $refs.runButtonPopover.$emit('close')">
                    <template slot="error" slot-scope="error" v-if="error.error">
                        <div class="invalid-options">
                            {{ error.error.response.data.description }}

                            <ul>
                                <li v-for="option in error.error.response.data.invalid_options">
                                    {{ option }}
                                </li>
                            </ul>
                        </div>
                    </template>
                </submit-button>
                <b-popover target="plagiarism-run-button"
                           content="Not all mandatory options have been set!"
                           placement="left"
                           ref="runButtonPopover"
                           v-if="!allOptionsValid"/>
            </div>
        </div>
    </div>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';

import { cmpNoCase, readableFormatDate } from '@/utils';

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

        hidden: {
            type: Boolean,
            default: true,
        },
    },

    data() {
        return {
            providers: null,
            selectedProvider: null,
            selectedOptionsMap: new WeakMap(),
            selectedOptions: null,
            allOldAssignments: null,
            runs: null,
            oldSubmissions: null,
            runsPollingInterval: null,
            translateOptionSpecialCases: {
                provider: 'Provider',
                has_old_submissions: 'Old submission archive uploaded',
                has_base_code: 'Had base code uploaded',
                old_assignments: 'Old assignments',
            },
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
            return this.allOldAssignments.filter(assig => assig.id !== this.assignment.id);
        },
    },

    watch: {
        hidden: {
            immediate: true,
            handler() {
                if (!this.hidden && this.allOldAssignments === null) {
                    this.getOldAssignments();
                }
            },
        },

        selectedProvider(provider) {
            if (provider == null) {
                return;
            }

            if (this.selectedOptionsMap.get(provider) == null) {
                this.selectedOptionsMap.set(provider, this.makeOptions(provider));
            }

            this.selectedOptions = this.selectedOptionsMap.get(provider);

            // Old assignments are loaded using the watcher on `hidden`. That
            // should probably be changed when we have more than one provider.
        },

        $route(oldRoute, newRoute) {
            if (oldRoute.params.assignmentId !== newRoute.params.assignmentId) {
                this.selectedProvider = null;
                this.loadRuns();
            }
        },
    },

    methods: {
        showProgress(run) {
            const provider = this.providers.find(prov => prov.name === run.provider_name);
            return (
                (run.state === 'parsing' || run.state === 'running' || run.state === 'comparing') &&
                provider &&
                provider.progress
            );
        },

        translateOption(optName, run) {
            const provName = run.provider_name;
            if (optName in this.translateOptionSpecialCases) {
                return this.translateOptionSpecialCases[optName];
            }

            if (provName == null) {
                return optName;
            }
            const provider = this.providers.find(prov => prov.name === provName);
            return (
                provider.options.find(opt => opt.name === optName) || {
                    title: optName,
                }
            ).title;
        },

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

        runPlagiarismChecker() {
            const selectedOptions = Object.assign({}, this.selectedOptions);

            if (this.selectedOptions.old_assignments == null) {
                selectedOptions.old_assignments = [];
            } else {
                selectedOptions.old_assignments = this.selectedOptions.old_assignments.map(
                    assig => assig.id,
                );
            }

            let data;
            if (
                this.selectedProvider.options.some(
                    opt => opt.type === 'file' && selectedOptions[opt.name] != null,
                )
            ) {
                data = new FormData();

                this.selectedProvider.options.forEach(opt => {
                    if (opt.type === 'file') {
                        const optData = selectedOptions[opt.name];
                        selectedOptions[`has_${opt.name}`] = optData != null;
                        if (selectedOptions[opt.name] != null) {
                            data.append(opt.name, optData);
                        }
                        delete selectedOptions[opt.name];
                    }
                });
                data.append(
                    'json',
                    new Blob([JSON.stringify(selectedOptions)], {
                        type: 'application/json',
                    }),
                );
            } else {
                selectedOptions.has_base_code = false;
                selectedOptions.has_old_submissions = false;
                data = selectedOptions;
            }

            return this.$http.post(`/api/v1/assignments/${this.assignment.id}/plagiarism`, data);
        },

        afterRunPlagiarismChecker(response) {
            const run = response.data;
            run.formatted_created_at = readableFormatDate(run.created_at);
            this.runs.push(run);
        },

        async getOldAssignments() {
            const permissions = Object.entries(
                await this.$http
                    .get('/api/v1/permissions/?type=course&permission=can_view_plagiarism')
                    .then(({ data }) => data, () => {}),
            );

            let assignments = [];
            if (permissions.length) {
                assignments = (await Promise.all(
                    permissions.reduce((promises, [courseId, { can_view_plagiarism: canView }]) => {
                        if (canView) {
                            promises.push(
                                this.$http
                                    .get(`/api/v1/courses/${courseId}/assignments/`)
                                    .then(({ data }) => data, () => []),
                            );
                        }
                        return promises;
                    }, []),
                ))
                    .reduce((a, b) => a.concat(b))
                    .map(assig => {
                        const courseName = this.$htmlEscape(assig.course.name);
                        const assigName = this.$htmlEscape(assig.name);
                        assig.label = `${courseName} - ${assigName}`;
                        return assig;
                    })
                    .sort((a, b) => cmpNoCase(a.label, b.label));
            }

            this.allOldAssignments = assignments;
            this.providers.forEach(prov => {
                prov.options.forEach(opt => {
                    if (opt.name === 'old_assignments') {
                        opt.possible_options = this.oldAssignments;
                    }
                });
            });
        },

        addOldSubmissionsOption() {
            this.providers.forEach(provider => {
                provider.options.push({
                    name: 'old_submissions',
                    title: 'Old submissions',
                    description: `Code that should also be checked as old assignment(s) that is/are
                                  not yet in CodeGrade. This should be an archive whose top level
                                  entries are treated as a separate submission. The top level entry
                                  can either be a directory or archive whose contents count as a
                                  submission, or a single regular file which counts as the entire
                                  submission.`,
                    mandatory: false,
                    type: 'file',
                });
            });
        },

        addBaseCodeOption() {
            this.providers.forEach(provider => {
                if (provider.base_code) {
                    provider.options.push({
                        name: 'base_code',
                        title: 'Base code',
                        description: `Code to be excluded from plagiarism
                                      checking. This can be used to upload
                                      template code to reduce the amount of
                                      false positives.`,
                        mandatory: false,
                        type: 'file',
                    });
                }
            });
        },

        addOldAssignmentsOption() {
            for (let i = 0, l = this.providers.length; i < l; i++) {
                this.providers[i].options.push({
                    name: 'old_assignments',
                    title: 'Old assignments',
                    description:
                        'Include submissions from assignments from previous years in this run.',
                    type: 'multiselect',
                    mandatory: false,
                    possible_options: null,
                });
            }
        },

        runIsFinished(run) {
            return run.state === 'done' || run.state === 'crashed';
        },

        canGoToOverview(run) {
            return this.canView && this.runIsFinished(run);
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

            const { data: providers } = await this.$http.get('/api/v1/plagiarism/').catch(() => []);
            this.providers = providers;
            if (this.providers.length === 1) {
                [this.selectedProvider] = this.providers;
            }
        },

        async loadRuns() {
            if (!(this.canView || this.canManage)) {
                this.runs = [];
                return;
            }

            const { data: runs } = await this.$http
                .get(`/api/v1/assignments/${this.assignment.id}/plagiarism/`)
                .catch(() => []);
            runs.forEach(run => {
                run.formatted_created_at = readableFormatDate(run.created_at);
            });
            this.runs = runs;
        },

        pollRuns() {
            this.runsPollingInterval = setInterval(() => {
                const running = this.runs.filter(run => !this.runIsFinished(run));

                if (!running.length) {
                    return;
                }

                this.loadRuns();
            }, 1000);
        },

        deleteRun(run) {
            return this.$http.delete(`/api/v1/plagiarism/${run.id}`);
        },

        afterDeleteRun(run) {
            this.runs = this.runs.filter(r => r.id !== run.id);
        },
    },

    async mounted() {
        await Promise.all([this.loadProviders(), this.loadRuns()]);

        this.addOldAssignmentsOption();
        this.addOldSubmissionsOption();
        this.addBaseCodeOption();

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

<style lang="less" scoped>
@import '~mixins.less';

.plagiarism-runner > .loader {
    margin: 1rem;
    margin-bottom: 0;
}

.runs-table {
    &:last-child {
        margin-bottom: 0;
    }

    tr.run-done:hover,
    tr.run-crashed:hover {
        background-color: rgba(0, 0, 0, 0.075);
        cursor: pointer;
    }

    tr.run-crashed {
        td {
            border-color: lighten(@alert-danger-color, 30%);
            #app.dark & {
                border-color: @alert-danger-color;
            }
        }
        &:nth-of-type(2n + 1) {
            background: lighten(@alert-danger-color, 20%);
            #app.dark & {
                background: @alert-danger-color;
            }
        }
        &:nth-of-type(2n) {
            background: lighten(@alert-danger-color, 30%);
            #app.dark & {
                background: lighten(@alert-danger-color, 10%);
            }
        }
        &:hover {
            background: lighten(@alert-danger-color, 10%);
            #app.dark & {
                background: darken(@alert-danger-color, 10%);
                td {
                    border-color: darken(@alert-danger-color, 10%);
                }
            }
        }
    }

    td {
        vertical-align: middle;
    }

    .run-state {
        text-transform: capitalize;
        .loader {
            display: inline-block;
            margin-left: 0.5rem;
            transform: translateY(2px);
        }
    }

    .run-delete {
        white-space: nowrap;
        width: 1px;
        vertical-align: top;
    }
}

.selected-options-popover {
    text-align: left;

    ul {
        padding-left: 1rem;
        margin-bottom: 0;
    }
}

.providers-table {
    margin: 0;
}

.options-table {
    border-bottom: 1px solid rgba(0, 0, 0, 0.15);
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

.invalid-options {
    text-align: left;

    ul {
        padding-left: 1.25rem;
        margin-bottom: 0;
    }
}
.progress-text {
    display: block;
}
</style>
