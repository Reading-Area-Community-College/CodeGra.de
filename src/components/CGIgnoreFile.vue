<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="cgignore-file">
    <div v-if="oldRemoteVersion && editable">
        <b-alert show variant="warning">
            A previous version of the submission validator was used. This old format
            is deprecated, and can no longer be edited. The contents of this old
            file are:
            <div class="old-cgignore">
                <pre>{{ oldCgignore }}</pre>
            </div>
        </b-alert>
        <submit-button :submit="deleteIgnore"
                       @after-success="afterUpdateIgnore"
                       variant="danger"
                       confirm="Are you sure you want to delete this old validator?"
                       label="Clear and use new version"/>
    </div>
    <div v-else-if="oldRemoteVersion">
        <pre>{{ oldCgignore }}</pre>
    </div>
    <div v-else-if="!editable && !policy">
        No validation set.
    </div>
    <b-form-group
        v-else
        class="policy-form"
        :class="policy ? '' : 'policy-form-only'"
        label-class="font-weight-bold pt-0 policy-form-label"
        label-cols="9"
        horizontal>
        <template slot="label">
            By default
            <description-popover
                hug-text
                description="This determines what happens to files by
                             default. 'Deny all files' denies all files by
                             default, which determines exactly which files a
                             student is allowed to upload. 'Allow all files'
                             allows all files by default, which allows you to
                             specify which files a student is not allowed to
                             upload. With both options you can specify required
                             files, that students must upload."/>
        </template>
        <b-btn v-if="summaryMode"
               size="sm"
               class="policy-btn"
               variant="primary">
            {{ policyOptions.find(x => x.value === policy).text }}
        </b-btn>
        <b-form-radio-group
            v-else
            class="option-button"
            :disabled="!editable || policyDisabled"
            v-b-popover.top.hover="policyDisabled && editable ? 'You cannot change the policy after you have created rules.' : ''"
            v-model="policy"
            size="sm"
            :options="policyOptions"
            button-variant="primary"
            buttons
            />
    </b-form-group>
    <transition :name="disabledAnimations ? '' : 'collapse'">
        <div v-if="policy" class="collapse-entry">
            <table v-if="!summaryMode" class="table table-striped">
                <thead>
                    <tr>
                        <th colspan="2">Options</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="option in options">
                        <td>
                            {{ option.name }} <description-popover hug-text :description="option.description"/>
                        </td>
                        <td>
                            <b-form-group horizontal
                                          style="margin: 0;"
                                          label-cols="9"
                                          :label-for="option.id"
                                          >
                                <b-form-radio-group
                                    :id="option.id"
                                    class="option-button"
                                    size="sm"
                                    :disabled="!editable"
                                    v-model="option.value"
                                    :options="option.options"
                                    button-variant="primary"
                                    buttons
                                    />
                            </b-form-group>
                        </td>
                    </tr>
                </tbody>
            </table>
            <div>
                <div class="rules-header"><b>Exceptions and requirements</b></div>
                <ul class="rule-list striped-list"
                    v-if="!loadingRules"
                    :class="{ 'background-enabled': !disableBackgroundAnimation }"
                    >
                    <transition-group :name="disabledAnimations ? '' : 'list'">
                        <li v-for="ruleIndex in sortedRuleIndices"
                            v-if="!rules[ruleIndex].removed"
                            class="list-item"
                            :key="ruleIndex">
                            <div class="rule-wrapper">
                                <file-rule v-model="rules[ruleIndex]" :all-rules="rules"
                                           :editing="!!rules[ruleIndex].editing"
                                           :editable="editable"
                                           :policy="policy"
                                           :focus="!!rules[ruleIndex].focus"
                                           @file-sep-click="addNewRule"
                                           @done-editing="$set(rules[ruleIndex], 'editing', false)"/>
                                <b-button-group v-if="editable && !rules[ruleIndex].editing">
                                    <submit-button confirm="Are you sure you want to delete this rule?"
                                                   v-b-popover.top.hover="'Delete this rule'"
                                                   :submit="() => deleteRule(ruleIndex)"
                                                   :duration=0
                                                   :wait-at-least=0
                                                   variant="danger">
                                        <icon name="times"/>
                                    </submit-button>
                                    <b-btn variant="primary"
                                           class="edit-rule-btn"
                                           v-b-popover.top.hover="'Edit this rule'"
                                           @click="$set(rules[ruleIndex], 'editing', true)">
                                        <icon name="pencil"/>
                                    </b-btn>
                                </b-button-group>
                            </div>
                        </li>
                    </transition-group>
                    <li class="new-file-rule"
                        v-if="editable">
                        <file-rule v-model="newRule" editing
                                   :all-rules="rules"
                                   :policy="policy"/>
                    </li>
                </ul>
            </div>
            <div class="help-text" v-if="editable">
                <p>
                    Add rules by specifying the required, allowed or denied path
                    in the text area above. Use <code>/</code> or <code>\</code>
                    as a directory separator to specify that certain files are
                    required, allowed or denied in a directory. Start the rule
                    with a directory separator (<code>/</code>
                    or <code>\</code>) to specify that a file is required,
                    allowed or denied in the top level directory.
                </p>

                <p>
                    To match more than one file, you can use a single wildcard
                    for the name of the file, by using a <code>*</code>. For
                    example <code>/src/*.py</code> matches any file ending
                    with <code>.py</code> in the directory <code>src</code> that
                    is directly in the top level directory of the submission.
                </p>

            </div>

            <div v-if="editable">
                <hr/>
                <b-button-toolbar justify>
                    <submit-button :submit="deleteIgnore"
                                   @after-success="afterUpdateIgnore"
                                   variant="danger"
                                   confirm="Are you sure you want to delete this validator?"
                                   label="Delete"/>

                    <submit-button :submit="submitIgnore"
                                   @success="afterUpdateIgnore"
                                   class="submit-ignore"
                                   :disabled="!configurationValid">
                        <template slot="error" slot-scope="e">
                            <span v-if="getProps(e, null, 'error', 'response', 'data', 'code') === 'PARSING_FAILED'">
                                {{ e.error.response.data.message }}: {{ e.error.response.data.description }}
                            </span>
                            <span v-else-if="getProps(e, null, 'error', 'response', 'data', 'message')">
                                {{ e.error.response.data.message }}
                            </span>
                            <span v-else>
                                Something unknown went wrong!
                            </span>
                        </template>
                    </submit-button>
                </b-button-toolbar>
            </div>
        </div>
    </transition>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';

import { mapGetters, mapActions } from 'vuex';

import { range, getProps } from '@/utils';

import SubmitButton from './SubmitButton';
import FileRule from './FileRule';
import Loader from './Loader';
import DescriptionPopover from './DescriptionPopover';

let optionId = 0;
function getOptionId() {
    return `ignore-option-${optionId++}`;
}

export default {
    name: 'ignore-file',

    props: {
        assignmentId: {
            type: Number,
            required: true,
        },

        editable: {
            type: Boolean,
            default: true,
        },

        summaryMode: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        ...mapGetters('courses', ['assignments']),

        remoteIgnoreFile() {
            return [
                getProps(this.assignment, null, 'cgignore'),
                getProps(this.assignment, null, 'cgignore_version'),
            ];
        },

        policyDisabled() {
            return this.rules.some(r => !r.removed && r.rule_type !== 'require');
        },

        assignment() {
            return this.assignments[this.assignmentId];
        },

        configurationValid() {
            return (
                this.policy &&
                this.options.every(o => o.value != null) &&
                this.rules.some(r => !r.removed)
            );
        },

        sortedRuleIndices() {
            return range(this.rules.length).sort((indexA, indexB) => {
                const a = this.rules[indexA];
                const b = this.rules[indexB];

                if (a.name === '' || b.name === '') {
                    return b.name.length - a.name.length;
                } else if (a.name[0] === '/' && b.name[0] !== '/') {
                    return -1;
                } else if (a.name[0] !== '/' && b.name[0] === '/') {
                    return 1;
                }

                const partsA = a.name.split('/');
                const partsB = b.name.split('/');

                for (let i = 0; i < Math.min(partsA.length, partsB.length); ++i) {
                    const cmp = partsA[i].localeCompare(partsB[i]);
                    if (cmp !== 0) {
                        return cmp;
                    }
                }
                const lengthDiff = partsA.length - partsB.length;
                if (lengthDiff !== 0) {
                    return lengthDiff;
                }
                // Make sure we sort stable, by using the index as the tie breaker.
                return indexA - indexB;
            });
        },

        policyOptions() {
            return [
                { text: 'Deny all files', value: 'deny_all_files' },
                { text: 'Allow all files', value: 'allow_all_files' },
            ];
        },
    },

    watch: {
        newRule() {
            if (this.newRule.name) {
                this.rules.push(this.newRule);
                this.newRule = this.getNewRule();
            }
        },

        remoteIgnoreFile: {
            handler([file, version]) {
                this.copyRemoteValues(file, version);
            },
            immediate: true,
        },
    },

    mounted() {
        this.disabledAnimations = false;
    },

    data() {
        return {
            getProps,
            disableBackgroundAnimation: false,
            newRule: this.getNewRule(),
            deleting: false,
            disabledAnimations: true,
            policy: null,
            loadingRules: false,
            content: '',
            rules: [],
            options: this.getDefaultOptions(),
            oldRemoteVersion: false,
            oldCgignore: '',
        };
    },

    methods: {
        ...mapActions('courses', ['updateAssignment']),

        copyRemoteValues(ignore, version) {
            if (version === 'IgnoreFilterManager' || (version == null && ignore != null)) {
                this.oldCgignore = ignore;
                this.oldRemoteVersion = true;
                this.resetValues();
            } else if (version === 'EmptySubmissionFilter' || ignore == null) {
                this.oldRemoteVersion = false;
                this.resetValues();
            } else {
                this.oldRemoteVersion = false;
                this.policy = ignore.policy;
                this.rules = ignore.rules.map(r => Object.assign({}, r));
                this.options = this.getDefaultOptions().map(opt => {
                    const remote = ignore.options.find(o => o.key === opt.key);
                    if (remote != null) {
                        opt.value = remote.value;
                    }
                    return opt;
                });
            }
        },

        resetValues() {
            this.policy = null;
            this.rules = [];
            this.options = this.getDefaultOptions();
        },

        getDefaultOptions() {
            const onOff = [{ text: 'Enabled', value: true }, { text: 'Disabled', value: false }];

            return [
                {
                    key: 'delete_empty_directories',
                    description:
                        'If this option is enabled, this will automatically delete empty directories without any files in submissions.',
                    value: false,
                    name: 'Delete empty directories',
                    options: onOff,
                    id: getOptionId(),
                },
                {
                    key: 'remove_leading_directories',
                    description:
                        'If this option is enabled, this will automatically delete any extra leading directories in a submission. For example, if all the files and/or directories are in a subdirectory, this will remove the top level directory.',
                    value: true,
                    name: 'Delete leading directories',
                    options: onOff,
                    id: getOptionId(),
                },
                {
                    key: 'allow_override',
                    value: false,
                    description:
                        'If this option is enabled, this will allow students to press an override button to hand in a submission, even if it does not follow the hand-in requirements. Students will, however, get a warning that their submission does not follow the hand-in requirements.',
                    name: 'Allow overrides by students',
                    options: onOff,
                    id: getOptionId(),
                },
            ];
        },

        deleteIgnore() {
            return this.updateIgnore('', 'EmptySubmissionFilter');
        },

        submitIgnore() {
            return this.updateIgnore(
                {
                    policy: this.policy,
                    options: this.options.map(o => ({ key: o.key, value: o.value })),
                    rules: this.rules.filter(r => !r.removed).map(r => ({
                        name: r.name,
                        file_type: r.file_type,
                        rule_type: r.rule_type,
                    })),
                },
                'SubmissionValidator',
            );
        },

        updateIgnore(ignore, ignoreVersion) {
            const data = {
                ignore,
                ignore_version: ignoreVersion,
            };
            return this.$http
                .patch(`/api/v1/assignments/${this.assignment.id}`, data)
                .then(() => data);
        },

        addNewRule(name) {
            this.rules.push({
                name,
                file_type: name[name.length - 1] === '/' ? 'directory' : 'file',
                rule_type: 'require',
                editing: true,
                focus: true,
            });
            this.rules = this.rules;
        },

        async afterUpdateIgnore({ ignore, ignore_version: version }) {
            this.updateAssignment({
                assignmentId: this.assignmentId,
                assignmentProps: {
                    cgignore: ignore,
                    cgignore_version: version,
                },
            });
            // We need to set `loadingRules` to `true` so that we can update the
            // rules without having any issue with animations.
            this.loadingRules = true;
            await this.$nextTick();
            this.copyRemoteValues(ignore, version);
            this.loadingRules = false;
        },

        deleteRule(ruleIndex) {
            this.$set(this.rules[ruleIndex], 'removed', true);
            this.disableBackgroundAnimation = true;
            setTimeout(() => {
                this.disableBackgroundAnimation = false;
            }, 600);
        },

        getNewRule() {
            return {
                rule_type: 'require',
                file_type: 'directory',
                name: '',
            };
        },
    },

    components: {
        SubmitButton,
        FileRule,
        Icon,
        Loader,
        DescriptionPopover,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.rule-list.background-enabled .list-item {
    transition: all 0.3s;
}

td {
    vertical-align: middle;
}

.rule-wrapper {
    display: flex;
    justify-content: space-between;

    .submit-button {
        height: 100%;
        vertical-align: initial;
    }
}

.collapse-enter-active {
    transition: all 0.5s;
    max-height: 35rem;
    overflow: hidden;
}
.collapse-enter,
.collapse-leave-to,
.collapse-enter .collapse-entry {
    max-height: 0;
}

.list-enter-active {
    transition: all 0.9s;
    background-color: fade(@color-success, 50%) !important;
}
.list-leave-active {
    transition: opacity 0.6s;
    background-color: #d9534f !important;
}

.list-leave-to {
    background-color: #d9534f !important;
}
.list-enter,
.list-leave-to {
    opacity: 0;
}

.help-text {
    background-color: @footer-color;
    margin: 1rem 0;
    padding: 0.375rem 0.75rem;
    color: @text-color-muted;
    border-radius: 0.25rem;
    p:last-child {
        margin-bottom: 0;
    }
    #app.dark & {
        background-color: @color-primary-darker;
    }
}

.policy-form-only {
    margin-bottom: 0;
}

.old-cgignore {
    padding: 1rem;
    margin-top: 1rem;
    border: 1px solid currentColor;
    border-radius: 0.25rem;
}

pre {
    margin: 0;
    padding: 0;
}

.rules-header {
    border-top: 1px solid @color-border-gray-lighter;
    padding: 0.75rem;
    border-bottom: 2px solid @color-border-gray-lighter;
    #app.dark & {
        border-color: @color-primary-darker;
    }
}

.btn.policy-btn {
    float: right;
    cursor: default;
    box-shadow: none !important;

    &:hover {
        background-color: @color-primary;
    }
}

.btn.edit-rule-btn {
    margin-left: 0px;
}
</style>

<style lang="less">
@import '~mixins.less';

.cgignore-file {
    .option-button {
        .btn {
            border-color: @color-primary;
        }
        .btn:not(.disabled) {
            cursor: pointer;
            box-shadow: none;
        }
        &.btn-group {
            float: right;
        }
        .btn.active {
            text-decoration: underline;
            background-color: @color-primary;
        }
        .btn:not(.active) {
            background-color: @background-color;
            color: @text-color;
            #app.dark & {
                color: darken(@text-color-dark, 30%);
            }
            &:hover:not(.disabled) {
                background-color: darken(@background-color, 10%);
            }
        }
    }

    .policy-form {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        vertical-align: middle;
        margin-bottom: 0.75rem;
        .form-row {
            align-items: center;
        }
        .policy-form-label {
            padding-bottom: 0;
        }
    }
}
</style>
