<template>
<div class="file-rule"
     :class="editable ? 'editable' : ''">
    <div v-if="editing" class="rule-parts-wrapper">
        <b-form-select class="rule-selector"
                       v-if="!hideRuleType"
                       v-model="internalRuleType">
            <option value="require">
                required
            </option>
            <option value="deny" v-if="policy === 'allow_all_files'">
                denied
            </option>
            <option value="allow" v-else>
                allowed
            </option>
        </b-form-select>
        <span class="file-sep">
            <icon name="angle-double-right"/>
        </span>

        <b-input-group class="name-input-group">
            <input v-model="internalName"
                   ref="nameInput"
                   @keydown.ctrl.enter="emitInput"
                   class="form-control">

            <span v-b-popover.top.hover.window="invalidNameMessage"
                  slot="append">
                <b-btn @click="emitInput"
                       class="save-rule"
                       variant="primary"
                       :disabled="!internalNameValid">
                Save
            </b-btn>
        </span>
        </b-input-group>
    </div>
    <div v-else class="rule-parts-wrapper">
        <template v-if="!hideRuleType">
            <span class="special-part file-part rule-type"
                v-b-popover.top.hover.window="ruleTypeHelp">
                {{ readableRuleType }}
            </span>
            <span class="file-sep">
                <icon name="angle-double-right"/>
            </span>
        </template>

        <span class="file-part">
            <icon name="folder-open"/>
        </span>
        <span class="file-sep">
            <icon name="angle-right"/>
        </span>

        <template v-if="!fromRoot">
            <span class="special-part file-part dir-part"
                  v-b-popover.top.hover.window="nonRootDescription">
                anywhere
            </span>
            <span class="file-sep">
                <icon name="angle-right"/>
            </span>
        </template>

        <template v-for="part, index in dirParts">
            <span class="file-part dir-part">
                <pre>{{ part }}</pre>
            </span>

            <span class="file-sep click"
                  @click="editable && $emit('file-sep-click', `${fromRoot ? '/' : ''}${dirParts.slice(0, index + 1).join('/')}/`)">
                <icon name="angle-right"/>
            </span>
        </template>

        <span v-if="filePart && fileStarIndex >= 0" class="file-part name-with-wildcard">
            <span class="concrete-part" v-if="fileStarIndex > 0">
                <pre>{{ filePart.slice(0, fileStarIndex) }}</pre>
            </span><span class="wildcard" v-b-popover.top.hover.window="'This part of the name can be any string, or nothing.'">
                anything
            </span><span class="concrete-part" v-if="fileStarIndex + 1 < filePart.length">
                <pre>{{ filePart.slice(fileStarIndex  + 1) }}</pre>
            </span>
        </span>
        <span v-else-if="filePart" class="file-part name">
            <pre>{{ filePart }}</pre>
        </span>
        <span v-else class="file-part name special-part text"
              v-b-popover.top.hover.window="directoryDescription">
            any file
        </span>
    </div>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/folder-open';
import 'vue-awesome/icons/angle-right';
import 'vue-awesome/icons/angle-double-right';

export default {
    name: 'file-rule',

    props: {
        value: {
            type: Object,
            required: true,
        },

        focus: {
            type: Boolean,
            default: false,
        },

        policy: {
            type: String,
            required: true,
        },

        allRules: {
            type: Array,
            required: true,
        },

        editing: {
            type: Boolean,
            default: true,
        },

        hideRuleType: {
            type: Boolean,
            default: false,
        },

        editable: {
            type: Boolean,
            default: true,
        },
    },

    data() {
        return {
            allParts: [],
            fromRoot: null,
            isDirPattern: null,
            internalName: '',
            internalRuleType: '',
        };
    },

    mounted() {
        if (this.focus && this.editing) {
            this.$nextTick(() => {
                const ref = this.$refs.nameInput;
                if (ref) {
                    ref.focus();
                }
            });
        }
    },

    watch: {
        name: {
            handler() {
                this.allParts = this.name.split('/').filter(a => a && a.search(/[^/\\ ]/) >= 0);
                this.fromRoot = this.name[this.name.search(/[^ ]/)] === '/';
                this.isDirPattern = this.value.file_type === 'directory';
                this.internalName = this.name;
            },
            immediate: true,
        },

        policy() {
            if (this.internalRuleType === 'allow') {
                this.internalRuleType = 'deny';
            } else if (this.internalRuleType === 'deny') {
                this.internalRuleType = 'allow';
            }
        },

        ruleType: {
            handler() {
                this.internalRuleType = this.ruleType;
            },
            immediate: true,
        },

        editing() {
            this.$nextTick(() => {
                const ref = this.$refs.nameInput;
                if (ref) {
                    ref.focus();
                }
            });
        },
    },

    methods: {
        emitInput() {
            if (this.internalNameValid) {
                const fn = this.normalizedInternalName;
                this.$emit('input', {
                    ...this.value,
                    rule_type: this.internalRuleType,
                    name: fn,
                    file_type: fn[fn.length - 1] === '/' ? 'directory' : 'file',
                });
                this.internalName = this.name;
                this.$emit('done-editing');
            }
        },
    },

    computed: {
        ruleType() {
            return this.value.rule_type;
        },

        readableRuleType() {
            if (this.value.rule_type === 'require') {
                return 'required';
            } else if (this.value.rule_type === 'allow') {
                return 'allowed';
            } else {
                return 'denied';
            }
        },

        ruleTypeHelp() {
            let typ;
            if (this.value.rule_type === 'require') {
                return `Atleast one ${
                    this.value.file_type
                } matching this rule is required to be present`;
            } else if (this.value.rule_type === 'allow') {
                typ = 'allowed';
            } else {
                typ = 'denied';
            }

            return `If a ${this.value.file_type} matches this rule, it is ${typ}.`;
        },

        invalidNameMessage() {
            const starIndex = this.internalName.indexOf('*');

            if (this.internalName.length < 1) {
                return 'The name cannot be empty.';
            } else if (this.internalName.search(/[^/\\ ]/) < 0) {
                return 'The name should contain at least one non slash.';
            } else if (
                starIndex > -1 &&
                (this.internalName.indexOf('/', starIndex) > -1 ||
                    this.internalName.indexOf('\\', starIndex) > -1)
            ) {
                return 'You cannot use a wildcard in the name of a directory.';
            } else if (this.amountWildcards > 1) {
                return 'You can use at most one wildcard.';
            } else if (
                this.normalizedInternalName
                    .split('/')
                    .some(x => x[0] === ' ' || x[x.length - 1] === ' ')
            ) {
                return 'Files may not end or start with a space.';
            } else if (
                this.allRules.some(
                    x => x !== this.value && !x.removed && x.name === this.normalizedInternalName,
                )
            ) {
                return 'This rule already exist, duplicate rules are not allowed.';
            } else {
                return '';
            }
        },

        internalNameValid() {
            return !this.invalidNameMessage;
        },

        normalizedInternalName() {
            return this.internalName
                .split(/[/\\]/g)
                .join('/')
                .replace(/\/\/+/g, '/');
        },

        name() {
            return this.value.name;
        },

        directoryDescription() {
            if (this.value.rule_type === 'allow') {
                return 'Any file or directory in this directory is allowed.';
            } else if (this.value.rule_type === 'require') {
                return 'This directory should exist, and it contain at least one file or directory.';
            } else if (this.value.rule_type === 'deny') {
                return 'This directory is not allowed.';
            }

            return '';
        },

        filePart() {
            return this.isDirPattern ? '' : this.allParts[this.allParts.length - 1];
        },

        fileStarIndex() {
            return this.filePart.indexOf('*');
        },

        amountWildcards() {
            let res = 0;
            for (let i = 0; i < this.internalName.length; ++i) {
                if (this.internalName[i] === '*') res++;
            }
            return res;
        },

        dirParts() {
            if (this.isDirPattern) {
                return this.allParts;
            }
            return this.allParts.slice(0, this.allParts.length - 1);
        },

        nonRootDescription() {
            const type = this.value.file_type;

            if (this.value.rule_type === 'allow') {
                return `This ${type} is allowed anywhere.`;
            } else if (this.value.rule_type === 'require') {
                if (type === 'directory') {
                    return 'This directory is required to exist, and it should contain at least one file or directory.';
                } else {
                    return 'This file is required to be somewhere in the submission.';
                }
            } else if (this.value.rule_type === 'deny') {
                return `This ${type} is not allowed anywhere.`;
            }

            return '';
        },
    },

    components: {
        Icon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.file-rule {
    width: 100%;
    .rule-parts-wrapper {
        display: flex;
    }
}

.rule-selector,
.save-rule,
.add-dir-part,
.delete-dir-part,
.concrete-part,
.wildcard,
.file-part {
    font-weight: 400;
    padding: 0.375rem 0.75rem;
    font-size: 1rem;
    line-height: 1.5rem;
    height: 2.5rem;
    border-radius: 0.25rem;
    box-shadow: none;
    vertical-align: initial;
}

#app.dark .file-part {
    background-color: @color-primary-darker;
    border-color: @color-primary-darkest;
}

#app.dark .special-part,
#app.dark .wildcard,
#app.dark .rule-selector {
    background-color: @color-primary-darkest;
    border-color: @color-primary-darkest;
}

.file-part {
    border: 1px solid transparent;
    border-color: #ccc;
    background: white;
    &.name-with-wildcard {
        padding: 0;
        height: 100%;
        display: inherit;
    }
    .concrete-part {
        border-radius: 0;
        &:first-child {
            border-right: 1px solid #ccc;
        }
        &:last-child {
            border-left: 1px solid #ccc;
        }
        #app.dark & {
            border-color: @color-primary-darkest;
        }
    }
    pre {
        display: inline;
        color: inherit;
    }
}

.file-sep {
    border: 1px solid transparent;
    font-weight: 400;
    line-height: 1.5;
    padding: 0.375rem 0.125rem;
    vertical-align: middle;
    margin: 0 2px;
    .file-rule.editable &.click {
        cursor: pointer;
    }
}

.fa-icon {
    vertical-align: middle;
}

.rule-selector,
.wildcard,
.special-part {
    font-weight: normal;
    font-variant: small-caps;
    color: @text-color-muted;
    #app.dark & {
        color: lighten(@text-color-muted, 10%);
    }
    font-style: italic;
}

.wildcard,
.special-part {
    user-select: none;
    cursor: help;
    background-color: @footer-color;
}

.rule-selector {
    width: 6.5em;
}

.rule-type {
    background: white;
    width: 6.5em;
    text-align: center;
}

.delete-dir-part {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}

.toolbar {
    margin-bottom: 5px;
    .toolbar-button-group {
        margin: 0 auto;
    }
}

.name-input-group {
    flex: 1;
}
</style>
