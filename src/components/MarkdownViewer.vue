<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="markdown-viewer">
    <loader v-if="loading"/>
    <b-alert class="error" variant="danger" show v-else-if="error">
        {{ error }}
    </b-alert>
    <floating-feedback-button
        v-else
        class="feedback-button-wrapper"
        :style="{ fontSize: `${fontSize}px`}"
        :fileId="fileId"
        :line="0"
        :feedback="feedback"
        @set-feedback="feedback = $event"
        :editable="editable"
        :can-use-snippets="canUseSnippets"
        :assignment="assignment"
        slot-description="file"
        snippet-field-above
        always-show-button>
        <div class="scroller form-control"
             :style="{ fontSize: `${fontSize}px`}">
            <inner-markdown-viewer :markdown="data"
                                   :show-code-whitespace="showWhitespace"/>
        </div>
    </floating-feedback-button>
</div>
</template>

<script>
import { loadCodeAndFeedback } from '@/utils';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import FloatingFeedbackButton from './FloatingFeedbackButton';
import Loader from './Loader';

export default {
    name: 'markdown-viewer',

    props: {
        assignment: {
            type: Object,
            default: null,
        },
        submission: {
            type: Object,
            default: null,
        },
        file: {
            type: Object,
            default: null,
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
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
    },

    data() {
        return {
            loading: true,
            data: null,
            feedback: {},
            error: null,
        };
    },

    computed: {
        fileId() {
            return this.file.id || this.file.ids[0] || this.file.ids[1];
        },
    },

    methods: {
        loadCode() {
            this.loading = true;
            this.data = {};
            this.error = null;
            loadCodeAndFeedback(this.$http, this.fileId)
                .then(
                    ({ code, feedback }) => {
                        this.data = code;
                        this.feedback = feedback['0'];
                    },
                    err => {
                        this.error = err;
                    },
                )
                .then(() => {
                    this.loading = false;
                });
        },
    },

    mounted() {
        this.loadCode();
    },

    watch: {
        fileId() {
            this.loadCode();
        },
    },

    components: {
        InnerMarkdownViewer,
        FloatingFeedbackButton,
        Loader,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';
.markdown-viewer {
    padding-right: 2px;
    padding-bottom: 1px;
    position: relative;
}

.scroller {
    padding: 1rem;
    width: 100%;
    height: 100%;

    overflow: auto;

    // Fixes performance issues on scrolling because the entire
    // code viewer isn't repainted anymore.
    will-change: transform;

    @media @media-no-large {
        flex: 0 1 auto;
        flex: 0 1 -webkit-max-content;
        flex: 0 1 -moz-max-content;
        flex: 0 1 max-content;
    }
}

.feedback-button-wrapper {
    max-height: 100%;
    display: flex;
    flex-direction: column;
}
</style>

<style lang="less">
.markdown-viewer .floating-feedback-button .feedback-button {
    margin: 1rem;
}
</style>
