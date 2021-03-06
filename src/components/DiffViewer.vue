<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-alert variant="danger" show v-if="error">
    <div v-html="error"></div>
</b-alert>
<loader class="text-center" v-else-if="loading"></loader>
<div class="diff-viewer form-control" v-else-if="diffOnly">
    <div v-for="(part, i) in changedParts"
         :key="`part-${i}-line-${part[0]}`">
        <hr v-if="i !== 0">
        <ol :class="{ 'show-whitespace': showWhitespace }"
            class="diff-part"
            :start="part[0] + 1"
            :style="{
                    paddingLeft: `${3 + Math.log10(part[1]) * 2/3}em`,
                    fontSize: `${fontSize}px`,
                    }">
            <li v-for="line in range(part[0], part[1])"
                :key="line"
                :class="lines[line].cls">
                <code v-html="lines[line].txt"/>
            </li>
        </ol>
    </div>
</div>
<div class="diff-viewer form-control" v-else>
    <ol :class="{ 'show-whitespace': showWhitespace }"
        class="scroller"
        :style="{
                paddingLeft: `${3 + Math.log10(lines.length) * 2/3}em`,
                fontSize: `${fontSize}px`,
                }">
        <li v-for="(line, i) in lines"
            :key="i"
            :class="line.cls">
            <code v-html="line.txt"/>
        </li>
    </ol>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/cog';
import DiffMatchPatch from 'diff-match-patch';

import { last, range } from '@/utils';
import { visualizeWhitespace } from '@/utils/visualize';

import decodeBuffer from '@/utils/decode';

import FeedbackArea from './FeedbackArea';
import LinterFeedbackArea from './LinterFeedbackArea';
import Loader from './Loader';
import Toggle from './Toggle';

export default {
    name: 'diff-viewer',

    props: {
        file: {
            type: Object,
            default: null,
        },
        fontSize: {
            type: Number,
            default: 12,
        },
        showWhitespace: {
            type: Boolean,
            default: true,
        },
        diffOnly: {
            type: Boolean,
            default: false,
        },
        context: {
            type: Number,
            default: 0,
        },
    },

    data() {
        return {
            code: '',
            lines: [],
            loading: true,
            error: false,
            canUseSnippets: false,
            range,
        };
    },

    mounted() {
        this.getCode();
    },

    watch: {
        file(f) {
            if (f) this.getCode();
        },
    },

    methods: {
        getCode() {
            this.loading = true;
            this.error = '';

            const promises = this.file.ids.map(id => {
                if (id) {
                    return this.$http.get(`/api/v1/code/${id}`, {
                        responseType: 'arraybuffer',
                    });
                } else {
                    return Promise.resolve('');
                }
            });

            Promise.all(promises)
                .then(
                    ([{ data: orig }, { data: rev }]) => {
                        let origCode;
                        let revCode;
                        try {
                            origCode = decodeBuffer(orig);
                            revCode = decodeBuffer(rev);
                        } catch (e) {
                            this.error = 'This file cannot be displayed';
                            return;
                        }

                        this.diffCode(origCode, revCode);
                    },
                    ({ response: { data: { message } } }) => {
                        this.error = message;
                    },
                )
                .then(() => {
                    this.loading = false;
                    this.$emit('load');
                });
        },

        diffCode(origCode, revCode) {
            const ADDED = 1;
            const REMOVED = -1;

            // This was copied from the diff-match-patch repository
            function diffText(text1, text2) {
                const dmp = new DiffMatchPatch();
                // eslint-disable-next-line no-underscore-dangle
                const { chars1, chars2, lineArray } = dmp.diff_linesToChars_(text1, text2);
                const diffs = dmp.diff_main(chars1, chars2, false);
                // eslint-disable-next-line no-underscore-dangle
                dmp.diff_charsToLines_(diffs, lineArray);
                return diffs;
            }

            const diff = diffText(origCode, revCode);
            const lines = [];

            diff.forEach(([state, text]) => {
                let cls = '';
                if (state === ADDED) {
                    cls = 'added';
                } else if (state === REMOVED) {
                    cls = 'removed';
                }
                text.split('\n').forEach((txt, i) => {
                    // Merge lines. The diff output will be:
                    // [[0, 'hello\n\n']], [-1, 'bye'], [1, 'thomas']]
                    // When diffing: `hello
                    //
                    // bye`
                    // with `hello
                    //
                    // thomas`
                    //
                    // And the output should be `hello
                    //
                    // - bye
                    // + thomas`
                    //
                    // Without this merging the output will contain an extra newline.
                    const line = { txt, cls };
                    if (i === 0 && lines.length > 0 && last(lines).txt === '') {
                        lines[lines.length - 1] = line;
                    } else {
                        lines.push(line);
                    }
                });
            });

            lines.forEach(line => {
                line.txt = this.$htmlEscape(line.txt);
            });

            if (lines.length < 5000) {
                lines.forEach(line => {
                    line.txt = visualizeWhitespace(line.txt);
                });
            }

            this.lines = lines;
        },

        getChangedParts() {
            const res = [];
            const end = this.lines.length;

            this.lines.forEach((line, i) => {
                const startLine = Math.max(i - this.context, 0);
                const endLine = Math.min(i + this.context + 1, end);

                if (line.cls !== '') {
                    if (res.length === 0) {
                        res.push([startLine, endLine]);
                    } else if (last(res)[1] > startLine - 2) {
                        last(res)[1] = endLine;
                    } else {
                        res.push([startLine, endLine]);
                    }
                }
            });

            return res;
        },
    },

    computed: {
        changedParts() {
            return this.getChangedParts();
        },
    },

    components: {
        Icon,
        FeedbackArea,
        LinterFeedbackArea,
        Loader,
        Toggle,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.diff-viewer {
    position: relative;
    padding: 0;
    background: #f8f8f8;

    #app.dark & {
        background: @color-primary-darker;
    }
}

ol {
    min-height: 5em;
    overflow-x: visible;
    background: @linum-bg;
    margin: 0;
    padding: 0;
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

    &.added {
        background-color: @color-diff-added-light !important;

        #app.dark & {
            background-color: @color-diff-added-dark !important;
        }
    }

    &.removed {
        background-color: @color-diff-removed-light !important;

        #app.dark & {
            background-color: @color-diff-removed-dark !important;
        }
    }

    &:hover {
        cursor: text;
    }

    #app.dark & {
        background: @color-primary-darker;
        border-left: 1px solid darken(@color-primary-darkest, 5%);
    }
}

code {
    color: @color-secondary-text;
    background: transparent;
    white-space: pre-wrap;

    #app.dark & {
        color: #839496;
    }

    li.added & {
        color: black !important;
    }

    li.removed & {
        color: black !important;
    }
}

.loader {
    margin-top: 2.5em;
    margin-bottom: 3em;
}

.diff-part {
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 0.25rem;
    z-index: 100;
    li:first-child {
        border-top-right-radius: 0.25rem;
    }
    li:last-child {
        border-bottom-right-radius: 0.25rem;
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.diff-viewer {
    .whitespace {
        opacity: 0;
        #app.dark & {
            color: @color-secondary-text;
        }
    }

    .show-whitespace .whitespace {
        opacity: 1;
    }
}
</style>
