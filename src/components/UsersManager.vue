<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<loader v-if="loading" page-loader/>
<div class="users-manager" v-else>
    <b-table striped
             ref="table"
             v-if="canListUsers"
             class="users-table"
             :items="filteredUsers"
             :fields="fields"
             :sort-compare="sortTable"
             sort-by="User">

        <template slot="User" slot-scope="item">
            <span class="username">{{item.value.name}} ({{item.value.username}})</span>
        </template>

        <template slot="CourseRole" slot-scope="item">
            <loader :scale="2" v-if="updating[item.item.User.id]"/>
            <b-dropdown :text="item.value.name"
                        disabled
                        class="role-dropdown"
                        v-b-popover.top.hover="'You cannot change your own role'"
                        v-else-if="item.item.User.name == userName"/>
            <b-dropdown :text="item.value.name"
                        class="role-dropdown"
                        :disabled="item.item.User.name == userName"
                        v-else>
                <b-dropdown-header>Select the new role</b-dropdown-header>
                <b-dropdown-item v-for="role in roles"
                                 @click="changed(item.item, role)"
                                 :key="role.id">
                    {{ role.name }}
                </b-dropdown-item>
            </b-dropdown>
        </template>
    </b-table>

    <b-alert show variant="danger" v-else>
        You can only actually manage users when you also have the 'list course
        users' ('can_list_course_users') permission
    </b-alert>

    <b-popover class="new-user-popover"
               :triggers="course.is_lti ? 'hover' : ''"
               target="new-users-input-field">
        You cannot add users to a lti course.
    </b-popover>
    <b-form-fieldset class="add-student"
                     id="new-users-input-field">
        <b-input-group>
            <user-selector v-model="newStudentUsername"
                           placeholder="New student"
                           :use-selector="canListUsers && canSearchUsers"
                           :extra-params="{ exclude_course: course.id }"
                           :disabled="course.is_lti"/>

            <template slot="append">
                <b-dropdown class="drop"
                            :text="newRole ? newRole.name : 'Role'"
                            :disabled="course.is_lti">
                    <b-dropdown-item v-for="role in roles"
                                     v-on:click="() => {newRole = role; error = '';}"
                                     :key="role.id">
                        {{ role.name }}
                    </b-dropdown-item>
                </b-dropdown>
                <submit-button class="add-user-button"
                               label="Add"
                               :submit="addUser"
                               @success="afterAddUser"
                               :disabled="course.is_lti"/>
            </template>
        </b-input-group>
    </b-form-fieldset>
</div>
</template>

<script>
import { mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/floppy-o';
import 'vue-awesome/icons/ban';

import { cmpNoCase, cmpOneNull, waitAtLeast } from '@/utils';
import Loader from './Loader';
import SubmitButton from './SubmitButton';
import UserSelector from './UserSelector';

export default {
    name: 'users-manager',
    props: {
        course: {
            type: Object,
            default: null,
        },

        filter: {
            type: String,
            default: '',
        },
    },

    data() {
        return {
            roles: [],
            users: [],
            loading: true,
            updating: {},
            newStudentUsername: null,
            canListUsers: false,
            canSearchUsers: false,
            newRole: '',
            error: '',
            fields: {
                User: {
                    label: 'Name',
                    sortable: true,
                    key: 'User',
                },
                CourseRole: {
                    label: 'role',
                    sortable: true,
                    key: 'CourseRole',
                },
            },
        };
    },

    computed: {
        ...mapGetters('user', {
            userName: 'name',
        }),

        courseId() {
            return this.course.id;
        },

        filteredUsers() {
            return this.users.filter(this.filterFunction);
        },
    },

    watch: {
        course(newVal, oldVal) {
            if (newVal.id !== oldVal.id) {
                this.loadData();
            }
        },
    },

    mounted() {
        this.loadData();
    },

    methods: {
        filterFunction(item) {
            if (!this.filter) {
                return true;
            }

            const terms = [item.User.name, item.User.username, item.CourseRole.name];
            return (this.filter || '')
                .toLowerCase()
                .split(' ')
                .every(word => terms.some(t => t.toLowerCase().indexOf(word) >= 0));
        },

        async loadData() {
            this.loading = true;

            [, , this.canListUsers, this.canSearchUsers] = await Promise.all([
                this.getAllUsers(),
                this.getAllRoles(),
                this.$hasPermission('can_list_course_users', this.courseId),
                this.$hasPermission('can_search_users'),
            ]);

            this.loading = false;
            this.$nextTick(() => {
                this.$refs.table.sortBy = 'User';
            });
        },

        sortTable(a, b, sortBy) {
            if (typeof a[sortBy] === 'number' && typeof b[sortBy] === 'number') {
                return a[sortBy] - b[sortBy];
            } else if (sortBy === 'User') {
                const first = a[sortBy];
                const second = b[sortBy];

                const ret = cmpOneNull(first, second);

                return ret === null ? cmpNoCase(first.name, second.name) : ret;
            } else if (sortBy === 'CourseRole') {
                const first = a.CourseRole;
                const second = b.CourseRole;

                const ret = cmpOneNull(first, second);

                return ret === null ? cmpNoCase(first.name, second.name) : ret;
            }
            return 0;
        },

        getAllUsers() {
            return this.$http.get(`/api/v1/courses/${this.courseId}/users/`).then(
                ({ data }) => {
                    this.users = data;
                },
                () => [],
            );
        },

        getAllRoles() {
            return this.$http.get(`/api/v1/courses/${this.courseId}/roles/`).then(({ data }) => {
                this.roles = data;
            });
        },

        changed(user, role) {
            for (let i = 0, len = this.users.length; i < len; i += 1) {
                if (this.users[i].User.id === user.User.id) {
                    this.$set(user, 'CourseRole', role);
                    this.$set(this.users, i, user);
                    break;
                }
            }
            this.$set(this.updating, user.User.id, true);
            const req = this.$http.put(`/api/v1/courses/${this.courseId}/users/`, {
                user_id: user.User.id,
                role_id: role.id,
            });

            waitAtLeast(250, req)
                .then(() => {
                    this.$set(this.updating, user.User.id, false);
                    delete this.updating[user.User.id];
                })
                .catch(err => {
                    // TODO: visual feedback
                    // eslint-disable-next-line
                    console.dir(err);
                });
        },

        addUser() {
            if (this.newRole === '') {
                throw new Error('You have to select a role!');
            } else if (this.newStudentUsername == null || this.newStudentUsername.username === '') {
                throw new Error('You have to add a non-empty username!');
            }

            return this.$http.put(`/api/v1/courses/${this.courseId}/users/`, {
                username: this.newStudentUsername.username,
                role_id: this.newRole.id,
            });
        },

        afterAddUser(response) {
            this.newRole = '';
            this.newStudentUsername = null;
            this.users.push(response.data);
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
        UserSelector,
    },
};
</script>

<style lang="less">
.users-table tr :nth-child(2) {
    text-align: center;
}

.users-table th,
.users-table td {
    &:last-child {
        width: 1px;
    }
}

.users-table td {
    vertical-align: middle;
}

.users-table .dropdown .btn {
    width: 10rem;
}

.add-student .drop .btn {
    border-radius: 0;
}

.new-user-popover button {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}

.username {
    word-wrap: break-word;
    word-break: break-word;
    -ms-word-break: break-all;

    -webkit-hyphens: auto;
    -moz-hyphens: auto;
    -ms-hyphens: auto;
    hyphens: auto;
}

.role-dropdown .dropdown-toggle {
    padding-top: 3px;
    padding-bottom: 4px;
}
</style>

<style lang="less">
.add-user-button {
    .btn {
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        height: 100%;
    }
}
</style>
