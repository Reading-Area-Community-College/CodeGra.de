<template>
<div class="floating-feedback-button">
    <slot/>
    <div>
        <b-button class="feedback-button"
                  @click="startEditingFeedback"
                  :class="{ hide: hasFeedback && !alwaysShowButton }"
                  v-b-popover.top.hover="`Edit feedback for this ${slotDescription}`"
                  v-if="editable">
            <icon name="edit"/>
        </b-button>
    </div>
    <feedback-area
        :class="{ 'feedback-editable': editable }"
        ref="feedbackArea"
        :editing="editingFeedback"
        :editable="editable"
        :feedback="feedback.msg"
        :author="feedback && feedback.author"
        :line="line"
        :file-id="fileId"
        :total-amount-lines="line + 1000"
        :forceSnippetsAbove="snippetFieldAbove"
        :can-use-snippets="canUseSnippets"
        :assignment="assignment"
        @editFeedback="editingFeedback = true"
        @feedbackChange="feedbackChange"
        v-if="hasFeedback"/>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/edit';

import FeedbackArea from './FeedbackArea';

export default {
    name: 'floating-feedback-button',

    data() {
        return {
            editingFeedback: false,
        };
    },

    props: {
        fileId: {
            type: Number,
            required: true,
        },

        line: {
            type: Number,
            required: true,
        },

        feedback: {
            type: Object,
            default: () => ({}),
        },

        editable: {
            type: Boolean,
            default: false,
        },

        canUseSnippets: {
            type: Boolean,
            default: false,
        },

        slotDescription: {
            type: String,
            default: 'cell',
        },

        alwaysShowButton: {
            type: Boolean,
            default: false,
        },

        snippetFieldAbove: {
            type: Boolean,
            default: false,
        },

        assignment: {
            type: Object,
            required: true,
        },
    },

    computed: {
        hasFeedback() {
            return this.feedback && this.feedback.msg != null;
        },
    },

    methods: {
        feedbackChange(event) {
            this.$emit('set-feedback', event);
            this.editingFeedback = false;
        },

        startEditingFeedback() {
            this.editingFeedback = true;
            if (!this.hasFeedback) {
                this.$emit('set-feedback', {
                    line: this.line,
                    msg: '',
                });
            }
            this.$nextTick(() => {
                const ref = this.$refs.feedbackArea;
                if (ref) {
                    const el = ref.$el.querySelector('textarea');
                    if (el) {
                        el.focus();
                    }
                }
            });
        },
    },

    components: {
        Icon,
        FeedbackArea,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.feedback-button.btn {
    position: absolute;
    top: 0;
    right: 0;

    transition-property: opacity, transform;
    transition-duration: @transition-duration;
    transform: scale(0);
    opacity: 0;

    .floating-feedback-button:hover &:not(.hide) {
        transform: scale(1);
        opacity: 1;
    }
}

.feedback-area-wrapper {
    margin-top: 0.5rem;
}

.feedback-editable {
    cursor: pointer;
}

.floating-feedback-button {
    position: relative;
}
</style>

<style lang="less">
.floating-feedback-button .feedback-area.edit.feedback-editable {
    padding-bottom: 0;
}
</style>
