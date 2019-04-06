<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="ipython-viewer">
    <loader v-if="loading"/>
    <b-alert class="error" variant="danger" show v-else-if="error">
        {{ error }}
    </b-alert>
    <div v-for="(cell, i) in outputCells"
         :key="`output-cell-${i}`"
         v-else
         :style="{ fontSize: `${fontSize}px` }"
         class="output-cell">
        <hr v-if="i > 0"/>
        <span class="input-data-prompt"
              v-if="cell.cell_type === 'code'">
            In [{{ cell.execution_count || 1 }}]:
        </span>
        <div class="inner-output-cell">
            <span v-if="cell.cell_type === 'markdown'"
                  class="markdown-wrapper">
                <floating-feedback-button
                    :fileId="fileId"
                    :line="cell.feedback_offset"
                    :feedback="feedback[cell.feedback_offset]"
                    :assignment="assignment"
                    @set-feedback="$set(feedback, $event.line, $event)"
                    :editable="editable"
                    :can-use-snippets="canUseSnippets">
                    <inner-markdown-viewer
                        :markdown="cell.source"
                        :show-code-whitespace="showWhitespace"/>
                </floating-feedback-button>
            </span>
            <div v-else-if="cell.cell_type === 'code'">
                <inner-code-viewer
                    class="code"
                    :assignment="assignment"
                    :code-lines="cell.source"
                    :feedback="feedback"
                    @set-feedback="$set(feedback, $event.line, $event)"
                    :linter-feedback="{}"
                    :show-whitespace="showWhitespace"
                    :font-size="fontSize"
                    :can-use-snippets="canUseSnippets"
                    :line-feedback-offset="cell.feedback_offset"
                    :file-id="Number(file.id)"
                    :editable="editable"
                    :warn-no-newline="false"/>
                <div v-for="out in cell.outputs"
                     :key="`cell-output-${out.feedback_offset}`"
                     class="result-cell">
                    <span class="output-data-prompt">
                        Out [{{ cell.execution_count || 1}}]:
                    </span>
                    <floating-feedback-button
                        :class="{'feedback-editable-output': editable}"
                        :assignment="assignment"
                        :fileId="fileId"
                        :line="out.feedback_offset"
                        :feedback="feedback[out.feedback_offset]"
                        @set-feedback="$set(feedback, $event.line, $event)"
                        :editable="editable"
                        :can-use-snippets="canUseSnippets">
                        <div class="inner-result-cell">
                            <span v-if="out.output_type === 'execute_result' || out.output_type === 'display_data'"
                                  class="mime-output">
                                <img v-if="outputData(out, ['png', 'image/png'])" :src="'data:image/png;base64,' + outputData(out, ['png', 'image/png'])"/>
                                <img v-else-if="outputData(out, ['jpeg', 'image/jpeg'])" :src="'data:image/jpeg;base64,' + outputData(out, ['jpeg', 'image/jpeg'])"/>
                                <span v-else-if="outputData(out, ['text/markdown'])">
                                    <inner-markdown-viewer :markdown="outputData(out, ['text/markdown'])"
                                                           :show-code-whitespace="showWhitespace"/>
                                </span>
                                <span v-else-if="outputData(out, ['text', 'text/plain'])">
                                    <pre>{{ outputData(out, ["text", "text/plain"]).join('') }}</pre>
                                </span>
                                <span v-else>
                                    <b style="color: red;">Unsupported output</b>
                                </span>
                            </span>
                            <pre v-else-if="out.output_type === 'stream'">{{ out.text }}</pre>
                            <pre v-else-if="out.output_type === 'error'">{{ out.traceback.join("\n") }}</pre>
                            <span v-else style="color: red;">
                                <b>Unknown output type:</b> {{ out.output_type }}
                            </span>
                        </div>
                    </floating-feedback-button>
                </div>
            </div>
        </div>
    </div>
</div>
</template>

<script>
import { highlightCode, loadCodeAndFeedback } from '@/utils';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import InnerCodeViewer from './InnerCodeViewer';
import FloatingFeedbackButton from './FloatingFeedbackButton';
import Loader from './Loader';

function maybeJoinText(txt) {
    if (Array.isArray(txt)) {
        return txt.join('');
    }
    return txt;
}

export default {
    name: 'ipython-viewer',

    props: {
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },
        file: {
            type: Object,
            required: true,
        },
        editable: {
            type: Boolean,
            required: false,
        },
        fontSize: {
            type: Number,
            default: 12,
        },
        showWhitespace: {
            type: Boolean,
            required: true,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        invalidJsonMessage: {
            type: String,
            default: 'The file is not a valid IPython notebook.',
        },
    },

    data() {
        return {
            data: {},
            loading: true,
            feedback: {},
            error: null,
        };
    },

    computed: {
        fileId() {
            return this.file.id || this.file.ids[0] || this.file.ids[1];
        },

        sourceLanguage() {
            if (this.data.metadata && this.data.metadata.language_info) {
                return this.data.metadata.language_info.name;
            }
            return 'python';
        },

        outputCells() {
            let curOffset = 0;

            return (this.data.cells || []).reduce((res, cell) => {
                if (cell.cell_type === 'raw') {
                    return res;
                }

                cell.source = maybeJoinText(cell.source);
                cell.feedback_offset = curOffset;
                res.push(cell);
                if (cell.cell_type === 'code') {
                    cell.source = highlightCode(cell.source.split('\n'), this.sourceLanguage);
                    curOffset += cell.source.length;
                    cell.outputs.forEach(out => {
                        out.feedback_offset = curOffset;
                        curOffset += 1;
                        if (out.output_type === 'stream') {
                            out.text = maybeJoinText(out.text);
                        }
                    });
                } else {
                    curOffset += 1;
                }
                return res;
            }, []);
        },
    },

    methods: {
        outputData(output, types) {
            for (let i = 0; i < types.length; ++i) {
                if (output.data[types[i]]) {
                    return output.data[types[i]];
                }
            }
            return null;
        },

        loadCode() {
            this.loading = true;
            this.data = {};
            loadCodeAndFeedback(this.$http, this.fileId)
                .then(
                    ({ code, feedback }) => {
                        try {
                            this.data = JSON.parse(code);
                        } catch (_) {
                            this.error = this.invalidJsonMessage;
                        }
                        this.feedback = feedback;
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
        InnerCodeViewer,
        InnerMarkdownViewer,
        FloatingFeedbackButton,
        Loader,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.output-cell {
    &:not(:last-child) {
        margin-bottom: 20px;
    }
    .code {
        border: 1px solid rgba(0, 0, 0, 0.1);
        padding-right: 0;
        overflow-x: hidden;
    }
    .code,
    .inner-result-cell {
        padding-right: 0.25rem;
        border-radius: 0.25rem;

        #app.dark & {
            border-color: @color-primary-darker;
        }

        li:first-child {
            border-top-right-radius: 0.25rem;
        }
        li:last-child {
            border-bottom-right-radius: 0.25rem;
        }
    }
    .inner-result-cell pre {
        padding: 0.6em 2rem;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 0.25rem;
        #app.dark & {
            background: @color-primary-darkest;
            color: @color-secondary-text-lighter;
        }
        margin-right: -0.25rem;
    }
    .input-data-prompt,
    .output-data-prompt {
        font-family: monospace;
        color: #999;
        width: 7em;
        margin-left: -10px;
        overflow-x: visible;
        display: block;
    }
    .output-data-prompt {
        margin-top: 10px;
        margin-bottom: 5px;
    }
}

.ipython-viewer {
    position: relative;
    padding: 0;
    border: 1px solid @color-border-gray-lighter;
    #app.dark & {
        border-color: @color-primary-darker;
    }
    border-radius: 0.25rem;
    padding: 15px;
}

pre {
    margin-bottom: 0;
    font-size: 100%;
    white-space: pre-wrap;
    word-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
}

.mime-output {
    overflow-x: auto;
}

.inner-result-cell img {
    max-width: 100%;
}

.inner-output-cell {
    position: relative;
}
</style>
