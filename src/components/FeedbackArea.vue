<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="feedback-area-wrapper non-editable" v-if="!editing">
    <div class="author" v-if="authorName">{{ authorName }}</div>
    <b-card class="feedback-area non-editable" :class="{'has-author': !!authorName}">
        <div @click="changeFeedback($event)" :style="{'min-height': '1em'}">
            <div v-html="newlines($htmlEscape(serverFeedback))"></div>
        </div>
    </b-card>
</div>
<div class="feedback-area edit" v-else @click.stop>
    <b-collapse class="collapsep"
                v-model="showSnippetDialog"
                v-if="canUseSnippets"
                :id="`collapse${line}`"
                style="margin: 0">
        <div>
            <b-input-group class="input-snippet-group">
                <input class="input form-control"
                       v-model="snippetKey"
                       :disabled="snippetDisabled"
                       @keydown.ctrl.enter="$refs.addSnippetButton.onClick"/>
                <b-input-group-append>
                    <submit-button ref="addSnippetButton"
                                   class="add-snippet-btn"
                                   :submit="addSnippet"
                                   @after-success="afterAddSnippet"
                                   @error="snippetDisabled = false">
                        <icon :scale="1" name="check"/>
                    </submit-button>
                </b-input-group-append>
            </b-input-group>
        </div>
    </b-collapse>

    <b-input-group
        class="editable-area"
        :style="{ 'margin-bottom': notSnippetsAbsoluteBelow && !showSnippetsAbove ?
                '11em' :
                undefined }">
        <div style="flex: 1; position: relative;">
            <b-card class="snippet-list-wrapper"
                    :class="{ 'snippets-above': showSnippetsAbove }"
                    v-if="possibleSnippets.length > 0">
                <span slot="header"
                      class="snippet-header">Snippets (press <kbd>Tab</kbd> to select the next item)</span>
                <ul :class="{ 'snippet-list': true, inline: line + 6 >= totalAmountLines, }">
                    <li class="snippet-item"
                        v-for="snippet, i in possibleSnippets"
                        :class="{ selected: snippetIndexSelected === i }"
                        ref="snippets"
                        :key="`snippet-key:${snippet.key}:${snippet.course}`"
                        @click="snippetIndexSelected = i">
                        <span v-if="snippet.course" class="snippet-icon"><icon :scale="0.9" name="book"/></span>
                        <span v-else class="snippet-icon"><icon :scale="0.9" name="user-circle-o"/></span>
                        <span>{{ snippet.key }}</span>
                        <span>- {{ snippet.value }}</span>
                    </li>
                </ul>
            </b-card>
            <textarea ref="field"
                      v-model="internalFeedback"
                      class="form-control editable-feedback-area"
                      :disabled="feedbackDisabled"
                      @keydown.esc.prevent="stopSnippets"
                      @keydown.exact.tab.prevent="maybeSelectNextSnippet(false)"
                      @keydown.exact.shift.tab.prevent="maybeSelectNextSnippet(true)"
                      @keydown="beforeKeyPress"
                      @keyup="updatePossibleSnippets"
                      @keydown.ctrl.enter.prevent="doSubmit"/>
        </div>
        <div class="minor-buttons btn-group-vertical">
                <b-btn class="snippet-btn"
                       variant="secondary"
                       v-if="canUseSnippets"
                       @click="findSnippet(); showSnippetDialog = !showSnippetDialog"
                       v-b-popover.top.hover="showSnippetDialog ? 'Hide snippet name' : 'Save as snippet'">
                    <icon name="plus"
                          aria-hidden="true"
                          :class="{ rotated: showSnippetDialog }"/>
                </b-btn>
                <submit-button :submit="deleteFeedback"
                               :filter-error="deleteFilter"
                               :duration="300"
                               @after-success="afterDeleteFeedback"
                               @error="deleteFeedbackError"
                               variant="danger"
                               ref="deleteButton"
                               v-b-popover.top.hover="'Delete feedback'">
                    <icon name="times" aria-hidden="true"/>
                </submit-button>
            </div>
            <b-input-group-append class="submit-feedback">
                <submit-button :submit="submitFeedback"
                               @success="afterSubmitFeedback"
                               @error="feedbackDisabled = false"
                               ref="submitButton"
                               v-b-popover.top.hover="'Save feedback'">
                    <icon name="check" aria-hidden="true"/>
                </submit-button>
            </b-input-group-append>
        </b-input-group>
    </div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/refresh';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/plus';

import { mapActions, mapGetters } from 'vuex';

import { nameOfUser } from '@/utils';
import SubmitButton from './SubmitButton';

export default {
    name: 'feedback-area',

    props: {
        line: {
            type: Number,
            required: true,
        },

        feedback: {
            type: String,
            required: true,
        },

        author: {
            type: [Object],
            required: false,
            default: undefined,
        },

        fileId: {
            type: Number,
            required: true,
        },

        editable: {
            type: Boolean,
            default: false,
        },

        editing: {
            type: Boolean,
            default: false,
        },

        canUseSnippets: {
            type: Boolean,
            default: false,
        },

        totalAmountLines: {
            type: Number,
            required: true,
        },

        forceSnippetsAbove: {
            type: Boolean,
            default: false,
        },

        assignment: {
            type: Object,
            required: true,
        },
    },

    data() {
        return {
            internalFeedback: this.feedback,
            serverFeedback: this.feedback,
            snippetKey: '',
            loadedSnippets: null,
            snippetIndexSelected: null,
            selectedSnippet: null,
            snippetOldKey: null,
            snippetDisabled: false,
            possibleSnippets: [],
            ignoreSnippets: null,
            showSnippetDialog: false,
            feedbackDisabled: false,
        };
    },

    async mounted() {
        if (this.editing) {
            this.loadedSnippets = false;
            await this.maybeRefreshSnippets();
            this.loadedSnippets = true;
        }

        this.$nextTick(() => {
            if (this.editing) {
                this.$refs.field.focus();
            }
        });
    },

    watch: {
        async editing() {
            this.loadedSnippets = false;
            await this.maybeRefreshSnippets();
            this.loadedSnippets = true;
        },

        snippetIndexSelected(_, oldVal) {
            // eslint-disable-next-line
            let [start, end] = this.snippetBound;
            let value;

            if (this.snippetIndexSelected === null) {
                if (this.selectedSnippet === null) {
                    return;
                }
                this.selectedSnippet = null;
                value = this.snippetOldKey;
                const oldSnip = this.possibleSnippets[oldVal];
                if (oldSnip != null) {
                    start = end - oldSnip.value.length;
                }
                const el = this.$refs.snippets[oldVal === 0 ? this.$refs.snippets.length - 1 : 0];
                if (el && el.scrollIntoView && !(this.$root.isEdge || this.$root.isSafari)) {
                    el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
                }
            } else {
                const newSnip = this.possibleSnippets[this.snippetIndexSelected];
                if (
                    !newSnip ||
                    (this.selectedSnippet != null &&
                        newSnip.key === this.selectedSnippet.key &&
                        newSnip.course === this.selectedSnippet.course)
                ) {
                    return;
                }

                [1, 0].forEach(i => {
                    const el = this.$refs.snippets[this.snippetIndexSelected + i];
                    if (el && el.scrollIntoView && !(this.$root.isEdge || this.$root.isSafari)) {
                        el.scrollIntoView({
                            block: 'nearest',
                            inline: 'nearest',
                            behavior: 'smooth',
                        });
                    }
                });

                this.selectedSnippet = newSnip;
                if (oldVal === null) {
                    this.snippetOldKey = this.internalFeedback.slice(start, end) || '';
                } else {
                    const oldSnip = this.possibleSnippets[oldVal];
                    start = end - oldSnip.value.length;
                }
                ({ value } = newSnip);
            }
            this.internalFeedback =
                this.internalFeedback.slice(0, start) + value + this.internalFeedback.slice(end);
        },
    },

    computed: {
        ...mapGetters({
            snippets: 'user/snippets',
            nameCurrentUser: 'user/name',
            findUserSnippetsByPrefix: 'user/findSnippetsByPrefix',
        }),

        snippetBound() {
            if (!this.editing || !this.internalFeedback) {
                return [0, 0];
            }
            const { selectionEnd } = this.$refs.field;

            const spaceIndex = this.lastWhiteSpace(this.internalFeedback, selectionEnd) + 1;
            if (this.ignoreSnippets != null && this.ignoreSnippets !== spaceIndex) {
                this.ignoreSnippets = null;
            }
            return [spaceIndex, selectionEnd];
        },

        notSnippetsAbsoluteBelow() {
            return this.possibleSnippets.length && this.line + 6 >= this.totalAmountLines;
        },

        showSnippetsAbove() {
            return this.forceSnippetsAbove || (this.notSnippetsAbsoluteBelow && this.line > 6);
        },

        authorName() {
            return nameOfUser(this.author);
        },
    },

    methods: {
        ...mapActions({
            maybeRefreshSnippets: 'user/maybeRefreshSnippets',
            addSnippetToStore: 'user/addSnippet',
            updateSnippetInStore: 'user/updateSnippet',
        }),

        lastWhiteSpace(str, start) {
            let i = start;
            for (; i > -1; i--) {
                const val = str[i];
                if (val === ' ' || val === '\n' || val === '\t') {
                    return i;
                }
            }
            return -1;
        },

        beforeKeyPress(event) {
            if (
                (event.key === 'Backspace' ||
                    event.keyIdentifier === 'Backspace' ||
                    event.keyCode === 8) &&
                (event.selectionStart !== event.selectionEnd || this.snippetIndexSelected !== null)
            ) {
                event.preventDefault();
                this.snippetIndexSelected = null;
            } else if (
                (event.key === 'Enter' ||
                    event.keyIdentifier === 'Enter' ||
                    event.keyCode === 13) &&
                this.snippetIndexSelected !== null
            ) {
                event.preventDefault();
                this.confirmSnippet();
            }
        },

        stopSnippets(event) {
            if (!this.possibleSnippets.length) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            this.snippetIndexSelected = null;
            this.$nextTick().then(() => {
                [this.ignoreSnippets] = this.snippetBound;
                this.possibleSnippets = [];
            });
            event.target.focus();
        },

        updatePossibleSnippets(event) {
            if (
                event.key === 'Tab' ||
                event.keyIdentifier === 'Tab' ||
                event.keyCode === 9 ||
                event.key === 'Shift' ||
                event.keyIdentifier === 'Shift' ||
                event.keyCode === 16 ||
                event.key === 'Alt' ||
                event.keyIdentifier === 'Alt' ||
                event.keyCode === 18 ||
                event.key === 'Escape' ||
                event.keyIdentifier === 'Escape' ||
                event.keyCode === 27 ||
                event.key === 'Control' ||
                event.keyIdentifier === 'Control' ||
                event.keyCode === 17
            ) {
                return;
            }
            if (
                event.key !== 'Delete' &&
                event.keyIdentifier !== 'Delete' &&
                event.keyCode !== 46
            ) {
                this.selectedSnippet = null;
            }
            if (!this.editing || !this.loadedSnippets || !this.internalFeedback) {
                this.possibleSnippets = [];
                return;
            }
            this.getPossibleSnippets();
        },

        getPossibleSnippets(force = false) {
            const [start, end] = this.snippetBound;
            this.snippetIndexSelected = null;
            if (start === this.ignoreSnippets || (!force && end - start < 3)) {
                this.possibleSnippets = [];
                return;
            }
            const word = this.internalFeedback.slice(start, end) || '';
            this.possibleSnippets = this.findSnippetsByPrefix(word);
        },

        findSnippetsByPrefix(word) {
            return [
                ...(this.assignment ? this.assignment.course.snippets : [])
                    .filter(snip => snip.key.startsWith(word))
                    .sort((a, b) => a.key.localeCompare(b.key))
                    .map(snip => Object.assign({}, snip, { course: true })),
                ...this.findUserSnippetsByPrefix(word),
            ];
        },

        async changeFeedback(e) {
            if (this.editable) {
                this.$emit('editFeedback', this.line);
                this.$nextTick(() => this.$refs.field.focus());
                this.internalFeedback = this.serverFeedback;
                e.stopPropagation();
                this.loadedSnippets = false;
                await this.maybeRefreshSnippets();
                this.loadedSnippets = true;
            }
        },

        focusInput() {
            this.$nextTick(() => {
                if (this.$refs.field) this.$refs.field.focus();
            });
        },

        doSubmit() {
            if (this.internalFeedback === '' || this.internalFeedback == null) {
                this.$refs.deleteButton.onClick();
            } else {
                this.$refs.submitButton.onClick();
            }
        },

        submitFeedback() {
            if (this.internalFeedback === '' || this.internalFeedback == null) {
                return this.deleteFeedback();
            }

            this.feedbackDisabled = true;

            const feedback = this.internalFeedback;
            return this.$http
                .put(`/api/v1/code/${this.fileId}/comments/${this.line}`, {
                    comment: feedback,
                })
                .then(() => feedback);
        },

        afterSubmitFeedback(feedback) {
            if (feedback === '' || feedback == null) {
                this.afterDeleteFeedback();
                return;
            }

            this.serverFeedback = feedback;
            this.feedbackDisabled = false;
            this.snippetKey = '';
            this.$emit('feedbackChange', {
                line: this.line,
                msg: feedback,
                author: { name: this.nameCurrentUser },
            });
        },

        submitFeedabckError() {
            this.feedbackDisabled = false;
        },

        newlines(value) {
            return value.replace(/\n/g, '<br>');
        },

        deleteFeedback() {
            this.feedbackDisabled = true;
            this.snippetKey = '';

            if (this.serverFeedback !== '') {
                return this.$http
                    .delete(`/api/v1/code/${this.fileId}/comments/${this.line}`)
                    .then(() => null);
            } else {
                return Promise.resolve();
            }
        },

        deleteFilter(err) {
            if (err.response && err.response.status === 404) {
                return err;
            } else {
                throw err;
            }
        },

        afterDeleteFeedback() {
            this.feedbackDisabled = false;

            this.$emit('feedbackChange', {
                line: this.line,
                msg: null,
                author: null,
            });
        },

        deleteFeedbackError() {
            this.feedbackDisabled = false;
        },

        confirmSnippet() {
            this.snippetIndexSelected = null;
            this.selectedSnippet = null;
            this.getPossibleSnippets();
        },

        maybeSelectNextSnippet(reverse) {
            if (!this.canUseSnippets) {
                return;
            }
            this.ignoreSnippets = null;

            const { selectionStart, selectionEnd } = this.$refs.field;

            if (selectionStart !== selectionEnd) {
                return;
            }

            const len = this.possibleSnippets.length;
            if (!len) {
                this.getPossibleSnippets(true);
                return;
            }

            if (this.snippetIndexSelected === null) {
                this.snippetIndexSelected = reverse ? len - 1 : 0;
            } else if (reverse && this.snippetIndexSelected === 0) {
                this.snippetIndexSelected = null;
            } else if (reverse) {
                this.snippetIndexSelected -= 1;
            } else if (this.snippetIndexSelected + 1 < len) {
                this.snippetIndexSelected += 1;
            } else {
                this.snippetIndexSelected = null;
            }
        },

        addSnippet() {
            const key = this.snippetKey;
            const value = this.internalFeedback;

            if (key.match(/\s/)) {
                throw new Error('No spaces allowed!');
            } else if (!key) {
                throw new Error('Snippet key cannot be empty');
            } else if (!value) {
                throw new Error('Snippet value cannot be empty');
            }

            this.snippetDisabled = true;

            if (key in this.snippets) {
                const { id } = this.snippets[key];
                return this.$http.patch(`/api/v1/snippets/${id}`, { key, value }).then(() => {
                    this.updateSnippetInStore({ id, key, value });
                });
            } else {
                return this.$http
                    .put('/api/v1/snippet', { key, value })
                    .then(({ data: newSnippet }) => {
                        this.addSnippetToStore(newSnippet);
                    });
            }
        },

        afterAddSnippet() {
            this.snippetDisabled = false;

            this.$root.$emit('bv::toggle::collapse', `collapse${this.line}`);
        },

        findSnippet() {
            if (this.snippetKey !== '' || this.showSnippetDialog) {
                return;
            }

            const keys = Object.keys(this.snippets);
            for (let i = 0, len = keys.length; i < len; i += 1) {
                if (this.internalFeedback === this.snippets[keys[i]].value) {
                    this.snippetKey = keys[i];
                    return;
                }
            }
        },
    },

    components: {
        Icon,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.snippet-list-wrapper {
    position: absolute;
    width: 100%;
    top: 100%;
    z-index: 2;
    margin: 0;

    &.snippets-above {
        position: absolute;
        top: -10.3em;
        height: 10.3em;
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        box-shadow: 0.2em -0.1em 0.5em 0 #ced4da;
        #app.dark & {
            box-shadow: 0.2em -0.1em 0.5em 0 @color-primary;
        }

        .snippet-header {
            height: 2em;
        }

        ~ .form-control {
            border-top-left-radius: 0;
        }
    }
    &:not(.snippets-above) {
        box-shadow: 0.2em 0.1em 0.5em 0 #ced4da;

        #app.dark & {
            box-shadow: 0.2em 0.1em 0.5em 0 @color-primary;
        }

        border-top-left-radius: 0;
        border-top-right-radius: 0;
        border-top: 0;

        ~ .form-control {
            border-bottom-left-radius: 0;
        }
    }

    .card-header {
        padding: 5px 15px;
        max-height: 2.3em;
    }
    .card-body {
        padding: 0;
        height: 100%;
    }
}

.snippet-list {
    margin: 0;
    max-height: 8em;
    padding: 0px;
    overflow-y: auto;

    .snippet-list-wrapper:not(.snippets-above) & {
        border-bottom-left-radius: 0.25rem;
        border-bottom-right-radius: 0.25rem;
    }
    &.inline {
        height: 8em;
    }

    .snippet-item {
        background: white;
        #app.dark & {
            background: @color-primary;
            color: white;
        }

        padding: 5px 15px;
        width: 100%;
        list-style: none;
        border-bottom: 1px solid rgba(0, 0, 0, 0.125);

        &:hover,
        &.selected {
            color: white;
        }
        &.selected {
            background: @color-secondary !important;
        }
        &:hover {
            background: lighten(@color-secondary, 20%) !important;
        }
        .snippet-list-wrapper.snippets-above &:first-child {
            border-top: 0;
        }
        .snippet-list-wrapper:not(.snippets-above) &:last-child {
            border-bottom: 0;
            padding-bottom: 5px;
        }
    }
}

.author {
    flex: 0 1 auto;
    padding: 0.5rem 10px;
    max-width: 20%;
    overflow: hidden;
    text-overflow: ellipsis;
}

.feedback-area-wrapper {
    .default-text-colors;
    background-color: white;

    #app.dark & {
        background-color: @color-primary-darker;
    }

    &.non-editable {
        display: flex;
        align-items: top;
        border: 1px solid rgba(0, 0, 0, 0.125);
        border-radius: 0.25rem;
    }
}

.feedback-area {
    &.non-editable {
        margin-top: 0;
        background-color: @footer-color;
        flex: 1 1 auto;
        &.has-author {
            border-top: 0;
            border-right: 0;
            border-bottom: 0;
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }
        &:not(.has-author) {
            border: 0;
        }

        #app.dark & {
            background-color: @color-primary;
            border-color: @color-primary-darkest;
        }
        white-space: pre-wrap;
        word-break: break-word;
    }

    &.edit {
        position: relative;
        padding-top: @line-spacing;
        padding-bottom: @line-spacing;
    }
}

.card-body {
    padding: 0.5rem;
}

button {
    border: none;
    box-shadow: none !important;
}

.minor-buttons {
    z-index: 1;
    &:hover {
        box-shadow: none;
    }
    button,
    .submit-button {
        flex: 1;
        &:first-child {
            border-top-right-radius: 0px;
            border-top-left-radius: 0px;
        }
    }
    min-height: 7em;
}

.collapsep {
    float: right;
    display: flex;
}

textarea {
    #app.dark & {
        border: 0;
    }
    min-height: 7em;
}

#app:not(.dark) .snippet-btn {
    border-top-width: 1px;
    border-top-style: solid;
}

.snippet-btn .fa-icon {
    transform: rotate(0);
    transition: transform @transition-duration;

    &.rotated {
        transform: rotate(45deg);
    }
}

.editable-area {
    #app.dark & {
        border: 0.5px solid @color-secondary;
    }
    padding: 0;
    border-radius: 0.25rem;
}

.input.snippet {
    margin: 0;
}

.input-snippet-group {
    padding-top: 0;
}

.editable-feedback-area {
    font-size: 1em;
    position: relative;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}

.snippet-icon {
    display: inline-block;
    width: 1rem;
    .fa-icon {
        vertical-align: middle;
        margin-top: -3px;
    }
}
</style>

<style lang="less">
.feedback-area .minor-buttons .submit-button.btn:last-child {
    border-bottom-right-radius: 0px;
    border-bottom-left-radius: 0px;
    border-top-right-radius: 0px;
    border-top-left-radius: 0px;
}
</style>
