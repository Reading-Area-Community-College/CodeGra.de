<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="image-viewer">
    <loader v-if="loading"/>
    <floating-feedback-button
        v-else-if="imgURL"
        :style="{ fontSize: `${fontSize}px` }"
        class="img"
        :fileId="id"
        :line="0"
        :feedback="feedback"
        @set-feedback="feedback = $event"
        :assignment="assignment"
        :editable="editable"
        :can-use-snippets="canUseSnippets"
        slot-description="image"
        snippet-field-above
        always-show-button>
        <img :src="imgURL"
             class="img form-control"
             :title="name"/>
    </floating-feedback-button>
    <b-alert variant="danger"
             :show="error !== ''">
        {{ error }}
    </b-alert>
</div>
</template>

<script>
import Loader from './Loader';
import FloatingFeedbackButton from './FloatingFeedbackButton';

export default {
    name: 'image-viewer',

    props: {
        file: {
            type: Object,
            required: null,
        },
        editable: {
            type: Boolean,
            required: false,
        },
        canUseSnippets: {
            type: Boolean,
            required: true,
        },
        fontSize: {
            type: Number,
            default: 12,
        },
        assignment: {
            type: Object,
            required: true,
        },
    },

    data() {
        return {
            imgURL: '',
            loading: true,
            error: '',
            feedback: {},
        };
    },

    watch: {
        id() {
            this.embedImg();
        },

        name() {
            this.embedImg();
        },
    },

    computed: {
        id() {
            return this.file ? this.file.id : -1;
        },

        name() {
            return this.file ? this.file.name : '';
        },
    },

    mounted() {
        this.embedImg();
    },

    methods: {
        embedImg() {
            this.loading = true;
            this.error = '';
            this.imgURL = '';
            Promise.all([
                this.$http.get(`/api/v1/code/${this.id}?type=feedback`).then(
                    ({ data: feedback }) => {
                        this.feedback = feedback['0'];
                    },
                    () => ({}),
                ),
                this.$http.get(`/api/v1/code/${this.id}?type=file-url`).then(
                    ({ data }) => {
                        this.imgURL = `/api/v1/files/${
                            data.name
                        }?not_as_attachment&mime=${this.getMimeType()}`;
                    },
                    ({ response }) => {
                        this.error = `An error occurred while loading the image: ${
                            response.data.message
                        }.`;
                    },
                ),
            ]).then(() => {
                this.loading = false;
            });
        },

        getMimeType() {
            const ext = this.name.split('.').reverse()[0];
            const types = {
                gif: 'image/gif',
                jpg: 'image/jpeg',
                jpeg: 'image/jpeg',
                png: 'image/png',
                svg: 'image/svg%2Bxml',
            };
            return types[ext];
        },
    },

    components: {
        Loader,
        FloatingFeedbackButton,
    },
};
</script>

<style lang="less" scoped>
.image-viewer {
    padding: 0;
    overflow: hidden;

    .img {
        max-width: 100%;
        max-height: 100%;
        padding: 0;
    }

    img.img {
        text-align: center;
        min-height: 0;
        object-fit: contain;
    }
}
</style>

<style lang="less">
.image-viewer .floating-feedback-button {
    display: flex;
    flex-direction: column;

    .feedback-button {
        margin: 1rem;
    }
}
</style>
