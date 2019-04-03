<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<ol :class="{ editable, 'lint-whitespace': assignment.whitespace_linter, 'show-whitespace': showWhitespace }"
    :start="computedStartLine"
    :style="{
            paddingLeft: `${3 + Math.log10(computedEndLine) * 2/3}em`,
            fontSize: `${fontSize}px`,
            }"
    class="hljs inner-code-viewer"
    @click="editable && addFeedback($event)">

    <li v-for="i in computedEndLine"
        v-if="i - 1 >= computedStartLine - 1 && (i < codeLines.length || codeLines[i - 1] !== '')"
        :key="i - 1"
        class="line"
        :class="{
                'linter-feedback-outer': $userConfig.features.linters && linterFeedback[i - 1],
                'feedback-outer': feedback[i - 1] != null }"
        :data-line="i">

        <code v-html="codeLines[i - 1]"/>

        <linter-feedback-area :feedback="linterFeedback[i - 1]"
                              v-if="$userConfig.features.linters &&
                                    linterFeedback[i - 1] != null"/>

        <feedback-area
            :editing="editing[i - 1]"
            :feedback="feedback[i - 1 + lineFeedbackOffset].msg"
            :author="feedback[i - 1 + lineFeedbackOffset].author"
            :editable="editable"
            :line="i - 1 + lineFeedbackOffset"
            :total-amount-lines="computedEndLine"
            :file-id="fileId"
            :can-use-snippets="canUseSnippets"
            :assignment="assignment"
            @editFeedback="editFeedback"
            @feedbackChange="feedbackChange"
            v-if="feedback[i - 1 + lineFeedbackOffset] && feedback[i - 1 + lineFeedbackOffset].msg !== null"/>
    </li>
    <li class="empty-file"
        v-if="codeLines.length === 1 && codeLines[0] === ''">
        File is empty.
    </li>
    <li class="missing-newline"
        v-if="warnNoNewline && computedEndLine === codeLines.length && codeLines[codeLines.length - 1] != ''">
        <icon name="level-up" style="transform: rotate(90deg)"/> Missing newline at the end of file.
    </li>
</ol>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/level-up';

import FeedbackArea from './FeedbackArea';
import LinterFeedbackArea from './LinterFeedbackArea';

export default {
    name: 'inner-code-viewer',
    props: {
        assignment: {
            type: Object,
            required: true,
        },

        codeLines: {
            type: Array,
            required: true,
        },

        feedback: {
            type: Object,
            required: true,
        },

        linterFeedback: {
            type: Object,
            default: () => ({}),
        },

        editable: {
            type: Boolean,
            default: false,
        },

        fontSize: {
            type: Number,
            default: 12,
        },

        showWhitespace: {
            type: Boolean,
            default: true,
        },

        fileId: {
            type: Number,
            required: true,
        },

        canUseSnippets: {
            type: Boolean,
            default: false,
        },

        startLine: {
            type: Number,
            default: 0,
        },

        endLine: {
            type: Number,
            default: null,
        },

        warnNoNewline: {
            type: Boolean,
            default: true,
        },

        lineFeedbackOffset: {
            type: Number,
            default: 0,
        },
    },

    data() {
        return {
            editing: {},
        };
    },

    computed: {
        computedStartLine() {
            return Math.max(this.startLine + 1, 1);
        },

        computedEndLine() {
            if (this.endLine === null) {
                return this.codeLines.length;
            }
            return Math.min(this.endLine, this.codeLines.length);
        },
    },

    components: {
        FeedbackArea,
        LinterFeedbackArea,
        Icon,
    },

    methods: {
        addFeedback(event) {
            const el = event.target.closest('li.line');
            if (!el) return;

            const line = Number(el.getAttribute('data-line')) - 1;

            if (!this.feedback[line] || !this.feedback[line].msg) {
                this.$emit('set-feedback', {
                    line: line + this.lineFeedbackOffset,
                    msg: '',
                });
            }
            this.$set(this.editing, line, true);

            this.$nextTick(() => {
                const feedbackArea = el.querySelector('.feedback-area textarea');
                if (feedbackArea) {
                    feedbackArea.focus();
                }
            });
        },

        feedbackChange(event) {
            this.$emit('set-feedback', event);
            this.$set(this.editing, event.line - this.lineFeedbackOffset, undefined);
        },

        editFeedback(event) {
            this.$set(this.editing, event - this.lineFeedbackOffset, true);
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

ol {
    margin: 0;
    padding: 0;
    overflow-x: visible;
    background: @linum-bg;
    font-family: monospace;
    font-size: small;

    #app.dark & {
        background: @color-primary-darkest;
        color: @color-secondary-text-lighter;
    }
}

li {
    position: relative;
    padding-left: 0.75em;
    padding-right: 0.75em;

    background-color: lighten(@linum-bg, 1%);
    border-left: 1px solid darken(@linum-bg, 5%);

    #app.dark & {
        background: @color-primary-darker;
        border-left: 1px solid darken(@color-primary-darkest, 5%);
    }

    &:hover {
        cursor: text;
    }

    .editable &:hover {
        cursor: pointer;
    }
}

code {
    border-bottom: 1px solid transparent;
    color: @color-secondary-text;
    white-space: pre-wrap;

    word-wrap: break-word;
    word-break: break-word;
    -ms-word-break: break-all;

    -webkit-hyphens: auto;
    -moz-hyphens: auto;
    -ms-hyphens: auto;
    hyphens: auto;

    #app.dark & {
        color: #839496;
    }

    ol.editable li:hover & {
        border-bottom-color: currentColor;
    }
}

.add-feedback {
    position: absolute;
    top: 0;
    right: 0.5em;
    display: none;
    color: black;

    li:hover & {
        display: block;
    }
}

.missing-newline,
.empty-file {
    list-style-type: none;
    cursor: default !important;
    user-select: none;

    svg {
        margin-bottom: -0.125em;
    }
}
</style>


<style lang="less">
@import '~mixins.less';

#app.dark ol.inner-code-viewer .btn:not(.btn-success):not(.btn-danger):not(.btn-warning) {
    background: @color-secondary;

    &.btn-secondary {
        background-color: @color-primary-darker;

        &:hover {
            background: @color-primary-darker;
        }
    }

    &:hover {
        background: darken(@color-secondary, 10%);
    }
}
</style>
