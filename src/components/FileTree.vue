<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="file-tree"
     :class="{ collapsed: isCollapsed, 'no-top-padding': showRevisions }">
    <div v-if="showRevisions"
         class="revision-container">

        <b-tabs small
                :value="selectedRevision"
                @input="revisionChanged"
                nav-class="revision-tabs"
                nav-wrapper-class="revision-tabs-wrapper">
            <b-tab v-for="option in revisionOptions"
                   :key="option.value"
                   :disabled="option.disabled"
                   v-b-popover.hover.bottom="'No rev'"
                   :title="option.title"/>
        </b-tabs>

        <description-popover placement="bottom">
            <span slot="description">
                Choose to view either the student's submitted files, the revised files as edited by a
                teacher or teaching assistant, or a diff between the two versions.

                <p v-if="!hasRevision(tree)" style="margin: 1rem 0 0;">
                    This submission has no revisions.
                </p>
            </span>
        </description-popover>
    </div>

    <div class="directory" :class="{ faded: depth > 0 && diffMode && !hasRevision(tree) }" @click.stop="toggle()">
        <span class="label"
              :title="tree.name">
            <icon name="caret-right" class="caret-icon" v-if="isCollapsed"
                  /><icon name="caret-down" class="caret-icon" v-else
                          /><icon name="folder" class="dir-icon" v-if="isCollapsed"
                                  /><icon name="folder-open" class="dir-icon" v-else
                                          /><slot name="dir-slot"
                                                  :depth="depth + 1"
                                                  :filename="tree.name"
                                                  :full-filename="`${fullName}/`"><span>{{ tree.name }}</span></slot>
            <sup v-if="depth > 0 && hasRevision(tree)"
                 v-b-popover.hover.top.window="'This directory has a file with a teacher\'s revision'"
                 class="rev-popover">
                modified
            </sup>
        </span>
    </div>
    <ol v-show="!isCollapsed" v-if="!isCollapsed || depth < 2">
        <li v-for="f in tree.entries"
            class="file"
            :class="{ faded: diffMode && !fileHasRevision(f), active: fileIsSelected(f) }">
            <file-tree :tree="f"
                       :collapsed="!fileInTree($route.params.fileId, f) && (collapseFunction && collapseFunction(`${fullName}/${f.name}/`))"
                       :collapse-function="collapseFunction"
                       :revision-cache="internalRevisionCache"
                       :no-links="noLinks"
                       :depth="depth + 1"
                       :parent-dir="fullName"
                        v-if="f.entries">
                <template v-for="slot in Object.keys($scopedSlots)" :slot="slot" slot-scope="scope">
                    <slot :name="slot" v-bind="scope"/>
                </template>
            </file-tree>
            <div v-else
                 class="label">
                <template v-if="noLinks">
                    <icon name="file" class="file-icon"/><slot name="file-slot"
                                                               :full-filename="`${fullName}/${f.name}`"
                                                               :filename="f.name"
                                                               :dir="tree"
                                                               :depth="depth"
                                                               >{{ f.name }}</slot>
                </template>
                <router-link :to="getFileRoute(f)"
                             v-else
                             :title="f.name">
                    <icon name="file" class="file-icon"/>{{ f.name }}
                </router-link>
                <sup v-if="fileHasRevision(f)"
                    v-b-popover.hover.top.window="revisionPopover(f)"
                    class="rev-popover">
                    <router-link :to="revisedFileRoute(f)"
                                :title="f.name"
                                @click="$emit('revision', 'diff')">
                        diff <code><small>(</small>{{ diffLabels[diffAction(f)] }}<small>)</small></code>
                    </router-link>
                </sup>
            </div>
        </li>
    </ol>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/folder';
import 'vue-awesome/icons/folder-open';
import 'vue-awesome/icons/file';
import 'vue-awesome/icons/caret-right';
import 'vue-awesome/icons/caret-down';

import { DescriptionPopover } from '@/components';

export default {
    name: 'file-tree',

    props: {
        tree: {
            type: Object,
            default: null,
        },
        collapsed: {
            type: Boolean,
            default: true,
        },
        collapseFunction: {
            type: Function,
            default: () => true,
        },
        depth: {
            type: Number,
            default: 0,
        },
        canSeeRevision: {
            type: Boolean,
            default: false,
        },
        revision: {
            type: String,
            default: 'student',
        },
        revisionCache: {
            type: Object,
            default: () => ({}),
        },
        noLinks: {
            type: Boolean,
            default: false,
        },
        parentDir: {
            type: String,
            default: '',
        },
    },

    data() {
        return {
            isCollapsed: this.collapsed,
            internalRevisionCache: { ...this.revisionCache },
            revisionOptions: [
                {
                    title: 'Student',
                    value: 'student',
                },
                {
                    title: 'Teacher',
                    value: 'teacher',
                },
                {
                    title: 'Diff',
                    value: 'diff',
                },
            ],
            diffLabels: {
                added: '+',
                changed: '~',
                deleted: '-',
            },
        };
    },

    computed: {
        courseId() {
            return this.$route.params.courseId;
        },

        fullName() {
            return `${this.parentDir}/${this.tree.name}`;
        },

        assignmentId() {
            return this.$route.params.assignmentId;
        },

        submissionId() {
            return this.$route.params.submissionId;
        },

        diffMode() {
            return !this.noLinks && this.$route.query.revision === 'diff';
        },

        selectedRevision() {
            let revision = this.revisionOptions.findIndex(opt => opt.value === this.revision);

            if (revision < 0 || this.revisionOptions[revision].disabled) {
                revision = 0;
            }

            return revision;
        },

        showRevisions() {
            return (
                !this.noLinks &&
                this.depth === 0 &&
                this.canSeeRevision &&
                (!this.tree.isStudent || this.hasRevision(this.tree))
            );
        },

        allRevisionCache() {
            return this.internalRevisionCache;
        },
    },

    methods: {
        toggle() {
            this.isCollapsed = !this.isCollapsed;
        },

        getFileRoute(file) {
            const fileId = file.id || file.ids[0] || file.ids[1];
            return {
                name: 'submission_file',
                params: {
                    courseId: this.courseId,
                    assignmentId: this.assignmentId,
                    submissionId: this.submissionId,
                    fileId,
                },
                query: this.$route.query,
            };
        },

        fileInTree(fileId, tree) {
            // This property depends on the return value of this function for
            // the parent. If the parent doesn't have the file in its tree this
            // component will also not have it.
            if (this.collapsed) {
                return false;
            }

            const todo = [...tree.entries];

            for (let i = 0; i < todo.length; i++) {
                const child = todo[i];
                if (child.entries) {
                    todo.push(...child.entries);
                } else if (Number(child.id) === Number(fileId)) {
                    return true;
                }
            }
            return false;
        },

        fileIsSelected(f) {
            const selectedId = this.$route.params.fileId;
            const fileId = f.id || (f.ids && (f.ids[0] || f.ids[1]));
            return Number(selectedId) === Number(fileId);
        },

        hasRevision(f) {
            if (this.internalRevisionCache[f.id] == null) {
                let res;
                if (f.entries) {
                    res = this.dirHasRevision(f);
                } else {
                    res = this.fileHasRevision(f);
                }

                this.internalRevisionCache[f.id] = res;
            }
            return this.internalRevisionCache[f.id];
        },

        fileHasRevision(f) {
            if (this.noLinks && f.entries) return false;

            return f.revision !== undefined || (f.ids && f.ids[0] !== f.ids[1]);
        },

        dirHasRevision(d) {
            if (d.revision !== undefined) {
                return true;
            }
            for (let i = 0; i < d.entries.length; i += 1) {
                if (this.hasRevision(d.entries[i])) {
                    return true;
                }
            }
            return false;
        },

        revisionChanged(index) {
            this.$emit('revision', this.revisionOptions[index].value);
        },

        revisedFileRoute(f) {
            let fileId;

            if (f.ids != null) {
                fileId = f.ids[1] == null ? f.ids[0] : f.ids[1];
            } else if (f.revision != null) {
                fileId = f.revision.id;
            } else if (f.revision === null) {
                fileId = f.id;
            } else {
                throw ReferenceError(`File '${f.name}' doesn't have a revision.`);
            }

            return {
                params: { fileId },
                query: Object.assign({}, this.$route.query, {
                    revision: 'diff',
                }),
            };
        },

        diffAction(f) {
            if (f.ids !== undefined) {
                if (f.ids[0] == null) {
                    return 'added';
                } else if (f.ids[1] == null) {
                    return 'deleted';
                } else {
                    return 'changed';
                }
            } else if (f.revision !== undefined) {
                if (f.revision == null) {
                    return 'deleted';
                } else {
                    return 'changed';
                }
            } else {
                throw ReferenceError(`File '${f.name} doesn't have a revision.`);
            }
        },

        revisionPopover(f) {
            const action = this.diffAction(f);
            return `This file was ${action} in the teacher's revision. Click here to see the diff`;
        },
    },

    components: {
        DescriptionPopover,
        Icon,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.file-tree a,
.file-tree {
    user-select: none;
    cursor: default;
    color: @color-primary;

    #app.dark & {
        color: @text-color-dark;
    }

    &.no-top-padding {
        padding-top: 0;
    }

    a:hover {
        cursor: pointer;
        text-decoration: underline;
    }

    .label {
        text-overflow: ellipsis;
        white-space: nowrap;
        overflow-x: hidden;
        display: block;
        max-width: 100%;
    }

    .directory .label:hover {
        cursor: pointer;
    }

    ol {
        list-style: none;
        margin: 0;
        padding: 0;
        padding-left: 1.2rem;
        overflow: hidden;
    }

    .file,
    .directory {
        &.faded > .label {
            opacity: 0.6;
        }

        &.active > .label {
            opacity: 1;
            font-weight: bold;
        }
    }

    .caret-icon {
        width: 1em;
    }

    .dir-icon {
        width: 1.5em;
    }

    .file-icon {
        width: 1em;
        margin-right: 0.5em;
    }

    .rev-popover {
        display: inline;
        font-weight: normal;
    }
}

.revision-container {
    position: relative;
    position: sticky;
    top: 0;
    margin: -0.5rem -0.75rem 0.875rem;
    padding: 0.5rem 0.75rem 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.15);
    background-color: @footer-color;

    #app.dark & {
        background-color: @color-primary-darker;
    }

    .tabs {
        flex: 1 1 auto;
        overflow: auto;
        margin: 0 -0.75rem -1px -0.75rem;
        padding: 0 0.75rem 0 0.75rem;

        .revision-tabs-wrapper {
            width: auto;
        }
    }

    .description-popover {
        position: absolute;
        top: 0;
        bottom: 0.75rem;
        right: 0;
        width: 1.5rem;
        padding-top: 0.95rem;
        background-color: inherit;
    }
}
</style>

<style lang="less">
.file-tree .revision-container {
    .revision-tabs-wrapper {
        width: max-content;
        padding-right: 1.75rem;
    }

    .revision-tabs {
        width: max-content;
        flex-wrap: nowrap;
    }

    .revision-tabs,
    .nav-link:hover,
    .nav-link.active {
        &,
        #app.dark & {
            border-bottom-color: transparent !important;
        }
    }

    .nav-link.disabled {
        cursor: not-allowed;
    }
}
</style>
