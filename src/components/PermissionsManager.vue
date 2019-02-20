<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader v-if="loading" page-loader/>
<div class="permissions-manager" v-else>
    <b-table striped
             class="permissions-table"
             :fields="fields"
             :items="items"
             :filter="filter"
             ref="permissionTable"
             :response="true">
        <template slot="name" slot-scope="item">
            <span v-if="item.value !== 'Remove'">
                {{ item.item.title }}
                <description-popover hug-text
                                     :icon="item.item._rowVariant === 'danger' ? 'exclamation-triangle' : undefined"
                                     placement="right">
                    <div slot="description"
                         class="permission-description">
                        <p>
                            {{ item.item.description }}
                        </p>
                        <p v-if="item.item.warning" >
                             <b class="text-danger">Warning:</b> {{ item.item.warning }}
                        </p>
                    </div>
                </description-popover>
            </span>
            <b v-else-if="showDeleteRole">{{ item.value }}</b>
        </template>
        <template v-for="(field, i) in fields"
                  :slot="field.key === 'name' ? `|||____$name$__||||${Math.random()}` : field.key"
                  slot-scope="item"
                  v-if="field.key != 'name'">
            <b-input-group v-if="item.item.name !== 'Remove'">
                <loader :scale="1"
                        v-if="item.item[field.key] === 'loading'"/>
                <span v-else-if="item.item.name === fixedPermission && field.own"
                      v-b-popover.top.hover="'You cannot disable this permission for yourself'">
                    <b-form-checkbox :checked="item.item[field.key]"
                                     disabled/>
                </span>
                <b-form-checkbox :checked="item.item[field.key]"
                                 @change="changeButton(item.item.name, field)"
                                 v-else/>
            </b-input-group>
            <b-input-group v-else-if="showDeleteRole">
                <submit-button label="Remove"
                               :ref="`delete-perm-${i}`"
                               variant="danger"
                               :submit="() => removeRole(i)"
                               @after-success="afterRemoveRole(i)"/>
            </b-input-group>
        </template>
    </b-table>
    <b-form-fieldset class="add-role" v-if="showAddRole">
        <b-input-group>
            <input v-model="newRoleName"
                   class="form-control"
                   placeholder="Name of new role"
                   @keyup.ctrl.enter="$refs.addUserBtn.onClick"/>

            <submit-button label="Add"
                           ref="addUserBtn"
                           :submit="addRole"
                           @after-success="afterAddRole"/>
        </b-input-group>
    </b-form-fieldset>

    <transition name="fade" appear>
        <!-- v-if and show are used to make sure the transition works -->
        <b-alert dismissible
                 show
                 v-if="!hideChanged && Object.values(changed).some(x => x)"
                 @input="hideWarning"
                 variant="info"
                 class="perm-warning">
            Reload the page to apply the changes.
        </b-alert>
    </transition>

</div>
</template>

<script>
import 'vue-awesome/icons/exclamation-triangle';

import { waitAtLeast } from '@/utils';

import DescriptionPopover from './DescriptionPopover';
import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'permissions-manager',

    props: {
        courseId: {},

        filter: {
            type: String,
            default: '',
        },

        fixedPermission: {
            default: 'can_edit_course_roles',
            type: String,
        },

        showDeleteRole: {
            type: Boolean,
            default: true,
        },

        showAddRole: {
            type: Boolean,
            default: true,
        },

        getRetrieveUrl: {
            type: Function,
            default: courseId => `/api/v1/courses/${courseId}/roles/?with_roles=true`,
        },

        getChangePermUrl: {
            type: Function,
            default: (courseId, roleId) => `/api/v1/courses/${courseId}/roles/${roleId}`,
        },

        getDeleteRoleUrl: {
            type: Function,
            default: (courseId, roleId) => `/api/v1/courses/${courseId}/roles/${roleId}`,
        },
    },

    data() {
        return {
            loading: true,
            fields: [],
            items: [],
            newRoleName: '',
            hideChanged: false,
            changed: {},
        };
    },

    watch: {
        courseId(newVal, oldVal) {
            if (newVal !== oldVal) {
                this.hideChanged = false;
                this.changed = {};
            }
            this.loadData();
        },
    },

    methods: {
        hideWarning() {
            this.hideChanged = true;
        },

        async loadData() {
            this.loading = true;
            await this.getAllPermissions();
            this.loading = false;
        },

        getAllPermissions() {
            return this.$http.get(this.getRetrieveUrl(this.courseId)).then(({ data }) => {
                const fields = [
                    {
                        key: 'name',
                        label: 'Name',
                        sortable: true,
                    },
                ];

                this.items = [];

                data.forEach(item => {
                    fields.push({
                        key: item.name,
                        label: item.name,
                        sortable: true,
                        id: item.id,
                        own: item.own,
                    });

                    let i = 0;
                    Object.entries(item.perms).forEach(([name, value]) => {
                        if (!this.items[i]) {
                            this.items[i] = {
                                name,
                                title: Permissions[name].short_description,
                                description: Permissions[name].long_description,
                                warning: Permissions[name].warning,
                                _rowVariant: Permissions[name].warning ? 'danger' : '',
                            };
                        }
                        this.items[i][item.name] = value;
                        i += 1;
                    });
                });

                if (this.showDeleteRole) {
                    this.items.push({ name: 'Remove' });
                }

                this.fields = fields;
            });
        },

        changeButton(permName, field) {
            let i = 0;
            for (let len = this.items.length; i < len; i += 1) {
                if (permName === this.items[i].name) {
                    break;
                }
            }
            const item = this.items[i];
            const newValue = !item[field.key];
            item[field.key] = 'loading';
            this.$set(this.items, i, item);
            const req = this.$http.patch(this.getChangePermUrl(this.courseId, field.id), {
                value: newValue,
                permission: item.name,
            });
            waitAtLeast(500, req).then(() => {
                this.hideChanged = false;
                this.$set(
                    this.changed,
                    `${this.courseId}-${field.id}-${item.name}`,
                    !this.changed[`${this.courseId}-${field.id}-${item.name}`],
                );
                item[field.key] = newValue;
                this.$set(this.items, i, item);
            });
        },

        removeRole(index) {
            const perm = this.fields[index];
            return this.$http
                .delete(this.getDeleteRoleUrl(this.courseId, perm.id))
                .then(() => index);
        },

        afterRemoveRole(index) {
            this.fields.splice(index, 1);
        },

        addRole() {
            if (this.newRoleName === '') {
                throw new Error('The name cannot be empty!');
            }

            return this.$http.post(`/api/v1/courses/${this.courseId}/roles/`, {
                name: this.newRoleName,
            });
        },

        afterAddRole() {
            this.getAllPermissions().then(() => {
                this.newRole = '';
                this.newRoleName = '';
            });
        },
    },

    mounted() {
        this.loadData();
    },

    components: {
        Loader,
        SubmitButton,
        DescriptionPopover,
    },
};
</script>

<style lang="less">
.permissions-manager {
    table.permissions-table {
        margin-bottom: 0;
        .delete .loader {
            height: 1.25rem;
        }

        tr {
            :first-child {
                vertical-align: middle;
            }
            :not(:first-child) {
                vertical-align: middle;
                text-align: center;
                .input-group {
                    align-items: center;
                    justify-content: center;
                }
            }
        }
    }
    .add-role {
        .btn {
            border-top-left-radius: 0;
            border-bottom-left-radius: 0;
        }
    }
}

.permission-description p:last-child {
    margin-bottom: 0;
}
</style>

<style lang="less" scoped>
@import '~mixins.less';

.add-role {
    margin-top: 1rem;
}

.perm-warning {
    position: fixed;
    bottom: 0;
    right: 1rem;
    z-index: 8;
    width: max-content;
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity @transition-duration;
}
.fade-enter,
.fade-leave-to {
    opacity: 0;
}
</style>
