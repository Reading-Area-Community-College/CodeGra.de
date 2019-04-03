<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader :scale="2" class="" v-if="loading"/>
<div class="snippet-manager" v-else>
    <b-form-group class="filter-group">
        <input v-model="filter"
               class="form-control"
               placeholder="Type to Search"
               v-on:keyup.enter="submit"/>
    </b-form-group>

    <table class="table table-striped snippets-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Replacement text</th>
                <th>
                    <b-button variant="primary"
                              class="add-button"
                              @click="editSnippet(null)"
                              v-b-popover.hover.top="'New snippet'">
                        <icon name="plus"/>
                    </b-button>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="snippet in filteredSnippets">
                <td class="snippet-key">{{ snippet.key }}</td>
                <td class="snippet-value">{{ snippet.value }}</td>
                <td class="snippet-actions">
                    <b-button-group>
                        <submit-button variant="danger"
                                       confirm="Are you sure you want to delete this snippet?"
                                       :submit="() => deleteSnippet(snippet)"
                                       @after-success="afterDeleteSnippet(snippet)"
                                       v-b-popover.hover.top="'Delete snippet'">
                            <icon name="times"/>
                        </submit-button>

                        <b-button variant="primary"
                                  @click="editSnippet(snippet)"
                                  v-b-popover.hover.top="'Edit snippet'">
                            <icon name="pencil"/>
                        </b-button>
                    </b-button-group>
                </td>
            </tr>
        </tbody>
    </table>

    <b-modal :title="modalTitle"
             ref="modal">
        <b-form-group v-if="!!editingSnippet">
            <b-input-group>
                <input type="text"
                       class="form-control"
                       placeholder="Name"
                       @input="setSaveConfirmMessage"
                       @keydown.ctrl.enter="clickSave"
                       v-model="editingSnippet.key"/>
            </b-input-group>
        </b-form-group>

        <b-form-group v-if="!!editingSnippet">
            <b-input-group>
                <textarea rows="10"
                          class="form-control"
                          placeholder="Replacement text"
                          @keydown.ctrl.enter="clickSave"
                          v-model="editingSnippet.value"/>
            </b-input-group>
        </b-form-group>

        <template slot="modal-footer">
            <b-button-toolbar justify
                              class="modal-buttons">
                <b-button variant="danger"
                          @click="cancelEditSnippet">
                    Cancel
                </b-button>

                <submit-button ref="saveButton"
                               :confirm="saveConfirmMessage"
                               :submit="saveSnippet"
                               @after-success="cancelEditSnippet">
                    Save
                </submit-button>
            </b-button-toolbar>
        </template>
    </b-modal>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/plus';

import { cmpNoCase } from '@/utils';

import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'snippet-manager',

    data() {
        return {
            loading: true,
            snippets: [],
            filter: '',
            editingSnippet: null,
            saveConfirmMessage: '',
        };
    },

    computed: {
        ...mapGetters('user', {
            storeSnippets: 'snippets',
        }),

        filteredSnippets() {
            if (!this.filter) {
                return this.snippets;
            } else {
                return this.snippets.filter(
                    s => s.key.match(this.filter) || s.value.match(this.filter),
                );
            }
        },

        modalTitle() {
            if (!this.editingSnippet) {
                return '';
            }
            return this.editingSnippet.id == null ? 'Add snippet' : 'Edit snippet';
        },
    },

    methods: {
        ...mapActions({
            refreshSnippets: 'user/refreshSnippets',
            addSnippetToStore: 'user/addSnippet',
            updateSnippetInStore: 'user/updateSnippet',
            deleteSnippetFromStore: 'user/deleteSnippet',
        }),

        editSnippet(snippet) {
            if (snippet == null) {
                this.editingSnippet = {
                    key: '',
                    value: '',
                };
            } else {
                this.editingSnippet = Object.assign({}, snippet);
            }

            this.$refs.modal.show();
        },

        cancelEditSnippet() {
            this.$refs.modal.hide();
        },

        clickSave() {
            this.$refs.saveButton.onClick();
        },

        ensureValidSnippet(snippet) {
            const { key, value } = snippet;

            if (!key) {
                throw new Error('The snippet name may not be empty.');
            }

            if (key.match(/\s/)) {
                throw new Error(
                    'Snippet names may not contain spaces. If you want to use ' +
                        'a multiple words in a name you can separate them with a ' +
                        'dash or an underscore.',
                );
            }

            if (!value) {
                throw new Error('The snippet replacement text may not be empty.');
            }
        },

        getSnippetWithSameKey(snippet) {
            const { id, key } = snippet;

            return this.snippets.find(s => s.key === key && s.id !== id);
        },

        isSnippetUnchanged(snippet) {
            const { id, key, value } = snippet;

            const oldSnippet = this.snippets.find(s => s.id === id);

            return oldSnippet && key === oldSnippet.key && value === oldSnippet.value;
        },

        findSnippetIndex(snippet) {
            return this.snippets.findIndex(s => s.id === snippet.id);
        },

        saveSnippet() {
            const snippet = this.editingSnippet;

            this.ensureValidSnippet(snippet);

            if (this.isSnippetUnchanged(snippet)) {
                return Promise.resolve(snippet);
            }

            const dup = this.getSnippetWithSameKey(snippet);
            if (dup) {
                const oldSnippet = Object.assign({}, snippet);
                snippet.id = dup.id;
                let req = this.updateSnippet(snippet);
                if (oldSnippet.id != null) {
                    req = req
                        .then(() => this.deleteSnippet(oldSnippet))
                        .then(this.afterDeleteSnippet);
                }
                return req;
            } else if (snippet.id == null) {
                return this.addSnippet(snippet);
            } else {
                return this.updateSnippet(snippet);
            }
        },

        addSnippet(snippet) {
            return this.$http.put('/api/v1/snippet', snippet).then(response => {
                snippet.id = response.data.id;
                this.addSnippetToStore(snippet);
                this.snippets.push(snippet);
            });
        },

        updateSnippet(snippet) {
            return this.$http.patch(`/api/v1/snippets/${snippet.id}`, snippet).then(() => {
                const idx = this.findSnippetIndex(snippet);
                this.updateSnippetInStore(snippet);
                this.snippets.splice(idx, 1, snippet);
            });
        },

        deleteSnippet(snippet) {
            return this.$http.delete(`/api/v1/snippets/${snippet.id}`).then(() => snippet);
        },

        afterDeleteSnippet(snippet) {
            const idx = this.findSnippetIndex(snippet);

            this.snippets.splice(idx, 1);
            this.deleteSnippetFromStore(snippet);
        },

        setSaveConfirmMessage() {
            const snippet = this.editingSnippet;

            if (snippet == null) {
                this.saveConfirmMessage = '';
            }

            const dup = this.getSnippetWithSameKey(snippet);

            if (dup) {
                let replacement = dup.value;
                if (replacement.length > 30) {
                    replacement = `${replacement.slice(0, 100)}...`;
                }

                this.saveConfirmMessage =
                    'There already exists a snippet with the same name and replacement text ' +
                    `"${replacement}". Do you want to overwrite that snippet?`;
            } else {
                this.saveConfirmMessage = '';
            }
        },
    },

    async mounted() {
        await this.refreshSnippets();
        this.loading = false;

        this.snippets = Object.values(this.storeSnippets).sort((a, b) => cmpNoCase(a.key, b.key));
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
.filter-group {
    padding: 0.75rem;
    margin-bottom: 0;
}

.snippets-table {
    margin-bottom: 0;

    th,
    td {
        vertical-align: middle;
    }

    .snippet-key {
        width: 25%;
    }

    .snippet-value {
        width: 75%;
        max-width: 0px;
        white-space: nowrap;
        text-overflow: ellipsis;
        overflow: hidden;
    }

    .snippet-actions {
        width: 0px;
        white-space: nowrap;
    }
}

.modal-content {
    .form-group:last-child {
        margin-bottom: 0;
    }

    .modal-buttons {
        flex: 1 1 auto;
    }
}

.add-button {
    width: 100%;

    .fa-icon {
        transform: translateY(3px) !important;
    }
}
</style>
