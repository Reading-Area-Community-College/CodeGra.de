<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="submission-uploader"
     :class="noBorder ? 'no-border' : ''">
    <b-modal id="wrong-files-modal"
             v-if="showWrongFileModal"
             hide-footer
             title="Your submission does not follow the hand-in instruction required by your teacher!">
        <div v-if="oldIgnoreFormat">
            <p>
                The following files should not be in your archive according to
                the <code style="margin: 0 0.25rem;">.cgignore</code> file. This
                means the following files are probably not necessary to hand
                in:
            </p>
            <ul class="wrong-files-list">
                <li style="margin-right: 2px; padding: 0.5em;" v-for="file in wrongFiles">
                    <code style="margin-right: 0.25rem">{{ file[0] }}</code> is ignored by <code>{{ file[1] }}</code>
                </li>
            </ul>
            <p>
                This could be a mistake so please make sure no necessary code is
                present in these files before you delete them!
            </p>
        </div>
        <div v-else class="wrong-files-modal-content">
            <b-tabs no-fade class="missing-required-files-tabs"
                    content-class="missing-required-files-content">
                <b-tab title="Missing files" class="ignore-tab" :disabled="wrongFileError.missing_files.length === 0">
                    <b-card class="ignore-card missing-card" no-body>
                        <p class="explanation">
                            The following files were required by your teacher, but
                            were not found in your submission.
                        </p>
                        <ul class="striped-list">
                            <li v-for="missing in wrongFileError.missing_files"
                                :key="missing.name">
                                <file-rule :value="missing"
                                           policy=""
                                           :editable="false"
                                           :all-rules="[]"
                                           :editing="false"
                                           hide-rule-type/>
                            </li>
                        </ul>
                    </b-card>
                </b-tab>
                <b-tab title="Denied files" class="ignore-tab"
                       :disabled="wrongFileError.removed_files.every(x => x.deletion_type === 'leading_directory')">
                    <b-card class="ignore-card denied-files" no-body>
                        <file-tree :tree="deheadedFileTree"
                                   :collapsed="false"
                                   :collapse-function="expandFileTree"
                                   no-links>
                            <template slot="file-slot"
                                      slot-scope="f">
                                <span class="deleted-file"
                                      v-b-popover.hover.top.window="'This file is denied.'"
                                      v-if="fileDeletionRule(f.fullFilename)"
                                      >{{ f.filename }}</span>
                                <span class="not-denied-file" v-else>{{ f.filename }}</span>
                            </template>
                            <template slot="dir-slot"
                                      slot-scope="f">
                                <span class="deleted-file"
                                      v-if="fileDeletionRule(f.fullFilename)"
                                      v-b-popover.top.hover.window="'This directory and all its files are denied.'"
                                      >{{ f.filename }}</span>
                                <span v-else-if="f.depth > 1 && dirContainsDeletions(f.fullFilename)"
                                      v-b-popover.top.hover.window="'This directory contains files which are denied.'"
                                      class="dir-with-deletions"
                                      >{{ f.filename }}</span>
                                <span :class="f.depth > 1 ? 'not-denied-file' : ''" v-else>{{ f.filename }}</span>
                            </template>
                        </file-tree>
                    </b-card>
                </b-tab>
                <b-tab title="Hand-in instructions" class="ignore-tab">
                    <b-card class="ignore-card" no-body>
                        <c-g-ignore-file :assignment-id="assignment.id"
                                         summary-mode
                                         :editable="false"/>
                    </b-card>
                </b-tab>
            </b-tabs>
        </div>
        <b-button-toolbar justify>
            <div v-b-popover.top.hover="canDeleteFiles ? '' : 'You are missing required files.'">
                <submit-button label="Delete files"
                            variant="danger"
                            :submit="() => overrideSubmit('delete')"
                            :disabled="!canDeleteFiles"
                            @after-success="afterOverrideSubmit"
                            @error="$emit('error', $event)"/>
            </div>

            <div v-b-popover.top.hover="canOverrideIgnore ? '' : (canDeleteFiles ? 'You are not allowed to override the hand-in requirements.' : 'You are missing required files.')">
                <submit-button label="Override"
                            variant="warning"
                            v-b-popover.top.hover="'hello'"
                            :submit="() => overrideSubmit('keep')"
                            :disabled="!canOverrideIgnore"
                            @after-success="afterOverrideSubmit"
                            @error="$emit('error', $event)"/>
            </div>

            <b-button variant="outline-primary"
                      @click="$root.$emit('bv::hide::modal', 'wrong-files-modal')">
                Cancel submission
            </b-button>
        </b-button-toolbar>
    </b-modal>

    <b-modal id="group-manage-modal"
             v-if="showGroupModal"
             hide-footer
             title="Group">
        <div class="group-modal-wrapper">
            <p class="header">
                This assignment is a group assignment. Each group should have at
                least {{ assignment.group_set.minimum_size }} members.

                <span v-if="currentGroup">
                    <span v-if="differentAuthor">{{ currentAuthor.name }} is</span>
                    <span v-else>You are</span>
                    currently member of a group with
                    {{ currentGroup.members.length }} members.
                </span>
                <span v-else>
                    <span v-if="differentAuthor">{{ currentAuthor.name }} is</span>
                    <span v-else>You are</span>
                    currently not member of any group.
                </span>
            </p>
            <p v-if="assignment.is_lti">
                This assignment is connected to an assignment in your
                {{ lmsName }}. This means that every user has to open the
                assignment at least once through {{ lmsName }}. Every user
                below <b>without</b> a check-mark next to their name should try
                to (re)open the assignment. If this issue persists, please
                contact CodeGrade support. You cannot submit while there are
                still members without a check-mark next to their name.
            </p>

            <div class="group-modal-body">
                <groups-management :assignment="assignment"
                                   :course="assignment.course"
                                   :group-set="assignment.group_set"
                                   :filter="currentGroup ? ((group) => currentGroup.id == group.id) : (() => true)"
                                   :show-lti-progress="currentGroup && assignment.is_lti ?
                                                       ((group) => currentGroup.id === group.id) :
                                                       (() => false)"
                                   @groups-changed="groupsChanged"
                                   :show-add-button="!currentGroup"/>
            </div>
        </div>

        <b-button-toolbar justify>
            <b-button variant="danger"
                      @click="$root.$emit('bv::hide::modal', 'group-manage-modal')">
                Cancel submission
            </b-button>

            <submit-button label="Try again"
                           :disabled="groupSubmitPossible"
                           :submit="trySubmitAgain"
                           @success="afterTrySubmitAgain"
                           @error="trySubmitAgainError"
                           />
        </b-button-toolbar>
    </b-modal>

    <vue-dropzone ref="submissionUploader"
                  id="submission-uploader"
                  class="dropzone"
                  :class="`dropzone-amount-files-${amountOfFiles}`"
                  :options="dropzoneOptions"
                  :use-custom-slot="true"
                  :include-styling="false"
                  @vdropzone-file-added="amountOfFiles++"
                  @vdropzone-removed-file="amountOfFiles--"
                  @vdropzone-drag-enter="dropzoneEntered"
                  @vdropzone-drag-leave="dropzoneLeft"
                  @vdropzone-drop="resetDragOverlay">
        <div v-if="showDropzoneOverlay" class="dz-hover-overlay"
             :class="{ hovered: dropzoneHovered }"/>

        <a class="dz-custom-message">
            Click here or drop file(s) to upload.
        </a>
    </vue-dropzone>

    <b-input-group>
        <user-selector v-if="forOthers"
                       v-model="author"
                       select-label=""
                       :disabled="disabled"
                       :base-url="`/api/v1/courses/${assignment.course.id}/users/`"
                       :use-selector="canListUsers"
                       :placeholder="`${defaultAuthor.name} (${defaultAuthor.username})`"/>
        <b-input-group-prepend v-else
                               is-text
                               class="deadline-information">
            The assignment is due {{ readableDeadline }}.
        </b-input-group-prepend>

        <submit-button class="submit-file-button"
                       :disabled="disabled || amountOfFiles === 0"
                       :confirm="confirmationMessage"
                       :submit="uploadFiles"
                       :filter-error="handleUploadError"
                       @success="afterUploadFiles"/>
    </b-input-group>
</div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';
import moment from 'moment';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';

import VueDropzone from 'vue2-dropzone';

import Loader from './Loader';
import SubmitButton, { SubmitButtonCancelled } from './SubmitButton';
import UserSelector from './UserSelector';
import GroupManagement from './GroupManagement';
import GroupsManagement from './GroupsManagement';
import FileRule from './FileRule';
import CGIgnoreFile from './CGIgnoreFile';
import FileTree from './FileTree';

let uploaderIndex = 0;

export default {
    name: 'submission-uploader',

    props: {
        assignment: {
            required: true,
            type: Object,
        },

        disabled: {
            default: false,
            type: Boolean,
        },

        forOthers: {
            type: Boolean,
            required: true,
        },

        canListUsers: {
            type: Boolean,
            required: true,
        },

        noBorder: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        ...mapGetters('user', { myUsername: 'username', myName: 'name' }),

        defaultAuthor() {
            return { name: this.myName, username: this.myUsername };
        },

        groupSubmitPossible() {
            return (
                !this.currentGroup ||
                this.currentGroup.members.length < this.assignment.group_set.minimum_size
            );
        },

        differentAuthor() {
            return !!(this.forOthers && this.author);
        },

        currentAuthor() {
            return this.differentAuthor ? this.author : this.defaultAuthor;
        },

        confirmationMessage() {
            if (
                this.forOthers &&
                (this.author == null || this.defaultAuthor.username === this.author.username)
            ) {
                return 'You are now submitting with yourself as author, are you sure you want to continue?';
            } else {
                return '';
            }
        },

        lmsName() {
            return this.assignment.lms_name;
        },

        oldIgnoreFormat() {
            return (
                this.assignment.cgignore_version == null ||
                this.assignment.cgignore_version !== 'SubmissionValidator'
            );
        },

        canDeleteFiles() {
            return this.oldIgnoreFormat || this.wrongFileError.missing_files.length === 0;
        },

        canOverrideIgnore() {
            return (
                this.oldIgnoreFormat ||
                (this.wrongFileError.missing_files.length === 0 &&
                    this.assignment.cgignore.options.some(
                        opt => opt.key === 'allow_override' && opt.value,
                    ))
            );
        },

        deheadedFileTree() {
            if (this.oldIgnoreFormat || !this.wrongFileError) {
                return {};
            } else if (
                this.wrongFileError.removed_files.length === 0 ||
                this.wrongFileError.removed_files[0].deletion_type !== 'leading_directory'
            ) {
                return this.wrongFileError.original_tree;
            } else {
                const tree = this.wrongFileError.original_tree;
                while (tree.entries.length === 1 && tree.entries[0].entries != null) {
                    tree.entries = tree.entries[0].entries;
                }
                return tree;
            }
        },

        uploadUrl() {
            let res = `/api/v1/assignments/${this.assignment.id}/submission?ignored_files=${
                this.ignored
            }`;
            if (this.differentAuthor) {
                res += `&author=${this.author.username}`;
            }
            return res;
        },

        dropzoneOptions() {
            return {
                url: this.uploadUrl,
                multiple: true,
                autoProcessQueue: false,
                createImageThumbnails: false,
                addRemoveLinks: true,
            };
        },

        readableDeadline() {
            return moment(this.assignment.deadline).from(this.$root.$now);
        },
    },

    data() {
        return {
            wrongFiles: [],
            wrongFileError: null,
            author: null,
            // This variable is a haxxxy optimization: Rendering a modal is SLOW
            // (!!) as it forces an entire reflow even when it is still
            // hidden. I most cases the modal on this page is never shown (it is
            // only shown when a user tries to hand in files that match the
            // ignore filters), so by default we don't render it (there is a
            // `v-if="showWrongFileModal"`) at all. When the modal is needed we
            // set this variable to `true`. We never reset this value back to
            // `false` as doing so f*cks the entire animation.
            showWrongFileModal: false,
            showGroupModal: false,
            ignored: 'error',
            showDropzoneOverlay: 0,
            dropzoneHovered: 0,
            amountOfFiles: 0,
            uploaderId: `submission-uploader-${uploaderIndex++}`,
            currentGroup: null,
            ruleCache: {},
        };
    },

    watch: {
        wrongFileError() {
            this.ruleCache = {};
        },
    },

    mounted() {
        document.body.addEventListener('dragenter', this.bodyDragEnter, true);
        document.body.addEventListener('dragleave', this.bodyDragLeave, true);
        document.body.addEventListener('mouseup', this.resetDragOverlay, true);
    },

    destroyed() {
        document.body.removeEventListener('dragenter', this.dropzoneEntered);
        document.body.removeEventListener('dragleave', this.dropzoneLeft);
        document.body.removeEventListener('mouseup', this.resetDragOverlay);

        // Make sure we don't leak the promise and event handler
        // set in the checkUpload method.
        this.$emit('warn-popover-hidden');
    },

    methods: {
        ...mapActions('courses', ['addSubmission']),

        getRequestData() {
            const data = new FormData();
            this.$refs.submissionUploader.getAcceptedFiles().forEach((f, i) => {
                data.append(`file${i}`, f);
            });
            return data;
        },

        expandFileTree(f) {
            return !(this.dirContainsDeletions(f) && !this.fileDeletionRule(f));
        },

        dirContainsDeletions(f) {
            const name = f.slice(this.deheadedFileTree.name.length + 2, f.length);
            // Extra slash to make sure we don't have name clashes in the cache.
            return this.fileDeletionRule(`${f}//`, other => other.startsWith(name));
        },

        fileDeletionRule(f, equals = (deletedFile, self) => deletedFile === self) {
            const name = f.slice(this.deheadedFileTree.name.length + 2, f.length);
            if (this.ruleCache[name] === undefined) {
                this.ruleCache[name] = null;
                for (let i = 0; i < this.wrongFileError.removed_files.length; ++i) {
                    const removed = this.wrongFileError.removed_files[i];
                    if (
                        removed.deletion_type !== 'leading_directory' &&
                        equals(removed.fullname, name)
                    ) {
                        this.ruleCache[name] = removed;
                    }
                }
            }

            return this.ruleCache[name];
        },

        resetDragOverlay() {
            this.dropzoneHovered = 0;
            this.showDropzoneOverlay = 0;
        },

        uploadFiles() {
            return this.$http.post(this.uploadUrl, this.getRequestData());
        },

        afterUploadFiles({ data: submission }) {
            this.addSubmission({
                assignmentId: this.assignment.id,
                submission,
            });
            this.$refs.submissionUploader.removeAllFiles();
            this.$emit('created', submission);
        },

        groupsChanged(newGroups) {
            for (let index = 0; index < newGroups.length; ++index) {
                const group = newGroups[index];
                const needle = this.currentAuthor.username;
                if (group.members.some(user => user.username === needle)) {
                    this.currentGroup = group;
                    return;
                }
            }
            this.currentGroup = null;
        },

        isArchiveError(err) {
            const { code } = err.response.data;
            return code === 'INVALID_FILE_IN_ARCHIVE';
        },

        isGroupError(err) {
            const { code } = err.response.data;
            return (
                code === 'INSUFFICIENT_GROUP_SIZE' || code === 'ASSIGNMENT_RESULT_GROUP_NOT_READY'
            );
        },

        handleUploadError(err) {
            if (this.isArchiveError(err) || this.isGroupError(err)) {
                this.uploadError(err);
                throw SubmitButtonCancelled;
            } else {
                throw err;
            }
        },

        async uploadError(err) {
            const { data } = err.response;
            this.ruleCache = {};

            if (this.isArchiveError(err)) {
                this.wrongFiles = data.invalid_files;
                this.wrongFileError = data;
                this.showWrongFileModal = true;
                await this.$nextTick();
                this.$root.$emit('bv::show::modal', 'wrong-files-modal');
            } else if (this.isGroupError(err)) {
                this.currentGroup = data.group;
                this.showGroupModal = true;
                await this.$nextTick();
                this.$root.$emit('bv::show::modal', 'group-manage-modal');
            }
        },

        overrideSubmit(type) {
            this.ignored = type;
            return this.uploadFiles();
        },

        afterOverrideSubmit(response) {
            this.ignored = 'error';
            this.afterUploadFiles(response);
            this.$root.$emit('bv::hide::modal', 'wrong-files-modal');
        },

        trySubmitAgain() {
            return this.uploadFiles();
        },

        afterTrySubmitAgain(response) {
            this.afterUploadFiles(response);
            this.$root.$emit('bv::hide::modal', 'wrong-files-modal');
            this.$root.$emit('bv::hide::modal', 'group-manage-modal');
        },

        trySubmitAgainError(response) {
            this.$emit('error', response);

            if (!this.isGroupError(response)) {
                this.uploadError(response);
            }
        },

        bodyDragEnter() {
            this.showDropzoneOverlay++;
        },

        bodyDragLeave() {
            if (this.showDropzoneOverlay > 0) {
                this.showDropzoneOverlay--;
            }
        },

        dropzoneEntered() {
            this.dropzoneHovered++;
        },

        dropzoneLeft() {
            if (this.dropzoneHovered > 0) {
                this.dropzoneHovered--;
            }
        },
    },

    components: {
        GroupManagement,
        GroupsManagement,
        SubmitButton,
        UserSelector,
        FileRule,
        Loader,
        CGIgnoreFile,
        FileTree,
        VueDropzone,
        Icon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.form-group {
    margin-bottom: 0;
}

.wrong-files-list {
    flex: 1 1 auto;
    list-style: none;
    margin-right: -0.95rem;
    overflow: auto;
}

.group-modal-wrapper {
    overflow: auto;
    border-bottom: 1px solid #e9ecef;
    margin: -0.95rem;
    margin-bottom: 0.95rem;
    padding: 0.95rem;
    min-height: 50vh;
}

.group-modal-body .groups-management {
    margin: 5px 0;
}

.btn-toolbar {
    flex: 0 0 auto;
}

.missing-card .explanation {
    padding: 0 0.75rem;
}

.ignore-card {
    padding-top: 0.75rem;
    border-top-right-radius: 0;
    border-top-left-radius: 0;
    border-top: 0;
    overflow-y: auto;
}

.ignore-tab {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
}

.missing-required-files-tabs {
    display: flex;
    flex-direction: column;
    min-height: 0;
}

.wrong-files-modal-content {
    overflow-y: hidden;
    display: flex;
    flex-direction: column;
    margin-bottom: 1rem;
}

.deleted-file {
    color: @color-diff-removed-dark;
    text-decoration: underline wavy;
}

.dir-with-deletions {
    text-decoration: underline wavy @color-diff-removed-dark;
}

.not-denied-file {
    opacity: 0.6;
}

.denied-files .file-tree {
    padding: 0.75rem;
    padding-top: 0;
}

.submit-file-button {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-bottom-left-radius: 0;
}
</style>

<style lang="less">
@import '~mixins.less';

.submission-uploader {
    &:not(.no-border) .dropzone {
        border: 1px solid #dee2e6;
        border-top-left-radius: 0.25rem;
        border-top-right-radius: 0.25rem;

        &.dropzone-amount-files-0 .dz-custom-message:hover {
            border-top-left-radius: 0.25rem;
            border-top-right-radius: 0.25rem;
        }

        .dz-message + .dz-preview,
        .dz-hover-overlay {
            border-top-left-radius: 0.25rem;
            border-top-right-radius: 0.25rem;
        }
    }

    &.no-border .user-selector .multiselect__tags {
        border-bottom: none;
        border-left: none;
    }

    .dropzone {
        position: relative;
        margin-bottom: -1px;
        padding-bottom: 4.5rem;

        #app.dark & {
            border-color: @color-primary-darker;
        }

        .dz-hover-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.25);
            pointer-events: none;

            &.hovered {
                background-color: rgba(0, 0, 0, 0.35);

                #app.dark & {
                    background-color: rgba(0, 0, 0, 0.4);
                }
            }

            &::after {
                content: 'Drop files here.';
                position: absolute;
                top: 0.75rem;
                left: 0.75rem;
                right: 0.75rem;
                bottom: 0.75rem;
                border: 2px dashed white;
                border-radius: 0.5rem;
                color: white;
                font-size: 2rem;
                text-align: center;
                display: flex;
                justify-content: center;
                align-items: center;

                #app.dark & {
                    color: @color-light-gray;
                    border-color: @color-light-gray;
                }
            }
        }

        .dz-custom-message {
            position: absolute;
            bottom: 0;
            width: 100%;
            height: 4.5rem;
            padding: 1.5rem;
            text-align: center;
            cursor: pointer;
            color: @color-primary;
            text-decoration: underline;

            &:hover {
                background-color: rgba(0, 0, 0, 0.075);
                text-decoration: underline;
            }
        }

        .dz-hover-overlay + .dz-custom-message {
            display: none;
        }

        .dz-preview {
            display: flex;
            padding: 0.75rem;
            border-bottom: 1px solid #dee2e6;

            #app.dark & {
                border-color: @color-primary-darker;
            }

            &:nth-child(2n) {
                background-color: rgba(0, 0, 0, 0.05);
            }
        }

        .dz-details {
            display: flex;
            font-size: 1rem;
            flex: 1 1 auto;
            flex-direction: row-reverse;
            justify-content: flex-end;
            min-width: 0;

            .dz-filename {
                flex: 1 1 auto;
                word-break: all;
                min-width: 0;
                span {
                    max-width: 100%;
                    text-overflow: ellipsis;
                    display: block;
                    overflow-x: hidden;
                }
            }

            .dz-size {
                flex: 0 0 auto;
                margin: 0 0.75rem;
            }
        }

        .dz-remove {
            flex: 0 0 auto;
            top: auto;
            bottom: auto;
            font-size: 0;
            margin: -0.25rem -0.5rem;
            padding: 0.25rem 0.5rem;
            text-decoration: none !important;

            &::after {
                content: '✖';
                font-size: 1rem;
                transition: all 250ms;
                color: @color-primary;
            }

            &:hover::after {
                color: @color-danger;
            }
        }

        .dz-image,
        .dz-progress,
        .dz-error-mark,
        .dz-success-mark,
        .dz-error-message {
            display: none;
        }
    }

    .deadline-information {
        flex: 1 1 auto;

        .input-group-text {
            width: 100%;
            background-color: transparent !important;

            #app.dark & {
                color: @text-color-dark !important;
            }
        }
    }

    .deadline-information .input-group-text,
    .multiselect .multiselect__tags {
        border-top-left-radius: 0;
        border-top-right-radius: 0;
    }

    #wrong-files-modal .modal-dialog {
        display: flex;
        flex-direction: column;
        height: auto;
        max-height: 75vh;
        min-width: 75vw;
        margin: 12.5vh auto;
        max-width: 768px;

        @media @media-small {
            max-height: ~'calc(100vh - 2rem)';
            margin: 1rem auto;
        }

        .missing-required-files-content {
            min-height: 0;
            display: flex;
            flex-direction: column;
        }
    }

    .modal-content {
        min-height: 0;
    }

    .modal-body {
        display: flex;
        flex-direction: column;
        min-height: 0;
    }
}
</style>
