<template>
<div v-if="error"
     class="plagiarism-detail">
    <b-alert show
             variant="danger"
             style="margin-top: 1rem;">
        {{ error }}
    </b-alert>
</div>
<loader v-else-if="loadingData || assignment == null"/>
<div class="plagiarism-detail" v-else>
    <local-header>
        <b-input-group-prepend slot="prepend"
                               @click="closeDetailView"
                               style="cursor: pointer;">
            <icon name="arrow-left"/>
        </b-input-group-prepend>
        <h4 slot="title" class="title">
            Plagiarism comparison for assignment &quot;{{assignment.name}}&quot;
        </h4>
        <b-input-group-append>
            <b-btn v-b-modal.plagiarism-export>Export</b-btn>
        </b-input-group-append>
    </local-header>

    <b-modal id="plagiarism-export" title="Export to LaTeX" hide-footer>
        <h6 style="text-align: center;">Select which matches should be exported</h6>
        <table class="range-table table table-striped table-hover">
            <thead>
                <tr>
                    <th>Export</th>
                    <th class="col-student-name">{{ detail.users[0].name }}</th>
                    <th class="col-student-range">Lines</th>
                    <th class="col-student-range">Color</th>
                    <th class="col-student-name">{{ detail.users[1].name }}</th>
                    <th class="col-student-range">Lines</th>
                </tr>
            </thead>

            <tbody>
                <tr v-for="match in matchesSortedByRange"
                    @click="$set(exportMatches, match.id, !exportMatches[match.id])">
                    <td><b-form-checkbox v-model="exportMatches[match.id]"/></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree1, match.files[0]) }}
                    <td class="col-student-range">{{ match.lines[0][0] + 1 }} - {{ match.lines[0][1] + 1 }}</td>
                    <td :style="`background: rgba(${match.color}, 0.4);`"></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree2, match.files[1]) }}
                    </td>
                    <td class="col-student-range">{{ match.lines[1][0] + 1 }} - {{ match.lines[1][1] + 1 }}</td>
                </tr>
            </tbody>
        </table>
        <b-button-toolbar justify style="margin-top: 1em;">
            <submit-button ref="submitExport"
                           label="Export"
                           @click="exportToLatex"/>
            <submit-button label="Cancel" default="outline-primary"
                           @click="$root.$emit('bv::hide::modal', 'plagiarism-export');"/>
        </b-button-toolbar>
    </b-modal>

    <div class="range-table-wrapper">
        <table class="range-table table table-striped table-hover">
            <thead>
                <tr>
                    <th class="col-student-name">{{ detail.users[0].name }}</th>
                    <th class="col-student-range">Lines</th>
                    <th class="col-student-range">Color</th>
                    <th class="col-student-name">{{ detail.users[1].name }}</th>
                    <th class="col-student-range">Lines</th>
                </tr>
            </thead>

            <tbody>
                <tr v-for="match in matchesSortedByRange"
                    @click="gotoLines(match.lines, match.files)">
                    <td class="col-student-name">
                        {{ getFromFileTree(tree1, match.files[0]) }}
                    <td class="col-student-range">{{ match.lines[0][0] + 1 }} - {{ match.lines[0][1] + 1 }}</td>
                    <td :style="`background: rgba(${match.color}, 0.4);`"></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree2, match.files[1]) }}
                    </td>
                    <td class="col-student-range">{{ match.lines[1][0] + 1 }} - {{ match.lines[1][1] + 1 }}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div v-if="!contentLoaded" style="padding-top: 3em;">
        <loader :scale="3"/>
    </div>
    <div class="code-viewer form-control" v-else>
        <pre>
            {{ getTexFile(detail.matches) }}
        </pre>
        <div class="student-files"
                v-for="key in ['self', 'other']"
                :ref="`file-comparison-${key}`">
            <b-card class="student-file"
                    v-for="file in sortedFiles"
                    v-if="filesPerStudent[key].includes(file.id.toString())"
                    :key="`file-comparison-${key}-${getFromFileTree(key == 'self' ? tree1 : tree2, file)}`"
                    :header="file.file_name"
                    :ref="`file-comparison-${key}-${getFromFileTree(key == 'self' ? tree1 : tree2, file)}`">
                <router-link v-if="detail.assignments[key == 'self' ? 0 : 1].id == assignment.id"
                             slot="header"
                             :to="fileRoute(file, key == 'self' ? 0 : 1)">
                             {{ getFromFileTree(key == 'self' ? tree1 : tree2, file) }}
                </router-link>
                <span v-else
                     slot="header"
                     class="link-disabled"
                     v-b-popover.hover.bottom="'You can\'t view files from other assignments.'">
                    {{ getFromFileTree(key == 'self' ? tree1 : tree2, file) }}
                </span>
                <ol class="form-control"
                    :style="{
                        paddingLeft: `${3 + Math.log10(file.content.length) * 2/3}em`,
                        fontSize: `${fontSize}px`,
                    }">
                    <li v-for="line in file.content">
                        <code v-html="line.colored || line"/>
                    </li>
                </ol>
            </b-card>
        </div>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/arrow-left';

import { Loader, LocalHeader, SubmitButton } from '@/components';

export default {
    name: 'plagiarism-detail',

    data() {
        return {
            detail: null,
            contentLoaded: false,
            tree1: null,
            tree2: null,
            sortedFiles: null,
            exportMatches: {},
            sortedFilesObject: {},
            loadingData: true,
            error: '',
        };
    },

    watch: {
        darkMode() {
            this.highlightAllLines();
        },

        $route(newRoute, oldRoute) {
            if (
                newRoute.params.assignmentId !== oldRoute.params.assignmentId ||
                newRoute.params.plagiarismRunId !== oldRoute.params.plagiarismRunId ||
                newRoute.params.plagiarismCaseId !== oldRoute.params.plagiarismCaseId
            ) {
                this.loadDetail();
            }
        },
    },

    computed: {
        ...mapGetters('pref', ['fontSize', 'darkMode']),

        ...mapGetters('courses', ['assignments']),

        colorPairs() {
            return [
                '#00FF00',
                '#FF0000',
                '#0000FF',
                '#FFFB00',
                '#00FFFF',
                '#7F00FF',
            ].map((color) => {
                const rgbInt = parseInt(color.slice(1), 16);
                const b = rgbInt & 0xFF;
                const g = (rgbInt >> 8) & 0xFF;
                const r = (rgbInt >> 16) & 0xFF;
                const background = [r, g, b];
                return {
                    background,
                    textColor: this.darkMode ?
                        background.map(item => Math.min(255, Math.max(25, item) * 4)) :
                        background.map(item => item / 1.75),
                };
            });
        },

        assignmentId() {
            return this.$route.params.assignmentId;
        },

        assignment() {
            return this.assignments[this.assignmentId];
        },

        plagiarismRunId() {
            return this.$route.params.plagiarismRunId;
        },

        plagiarismCaseId() {
            return this.$route.params.plagiarismCaseId;
        },

        userIds() {
            return [
                this.$route.params.userId1,
                this.$route.params.userId2,
            ];
        },

        filesPerStudent() {
            const self = {};
            const other = {};

            this.detail.matches.forEach((match) => {
                self[match.files[0].id] = true;
                other[match.files[1].id] = true;
            });

            return { self: Object.keys(self), other: Object.keys(other) };
        },

        matchesSortedByRange() {
            return this.detail.matches.sort(
                (a, b) => {
                    const lenA = (
                        (a.lines[0][1] - a.lines[0][0]) +
                        (a.lines[1][1] - a.lines[1][0])
                    ) / 2;
                    const lenB = (
                        (b.lines[0][1] - b.lines[0][0]) +
                        (b.lines[1][1] - b.lines[1][0])
                    ) / 2;
                    return lenB - lenA;
                },
            );
        },
    },

    methods: {
        ...mapActions('courses', ['loadCourses']),

        closeDetailView() {
            this.$router.push({
                name: 'plagiarism_overview',
                params: this.$route.params,
            });
        },

        async getTexFile(matches) {
            const header = `\\documentclass{article}
\\usepackage{listings}
\\usepackage{color}

\\definecolor{bluekeywords}{rgb}{0.13, 0.13, 1}
\\definecolor{greencomments}{rgb}{0, 0.5, 0}
\\definecolor{redstrings}{rgb}{0.9, 0, 0}
\\definecolor{graynumbers}{rgb}{0.5, 0.5, 0.5}


\\lstset{
    numbers=left,
    columns=fullflexible,
    showspaces=false,
    showtabs=false,
    breaklines=true,
    showstringspaces=false,
    breakatwhitespace=true,
    escapeinside={(*@}{@*)},
    commentstyle=\\color{greencomments},
    keywordstyle=\\color{bluekeywords},
    stringstyle=\\color{redstrings},
    numberstyle=\\color{graynumbers},
    basicstyle=\\ttfamily\\footnotesize,
    xleftmargin=12pt,
    rulesepcolor=\\color{graynumbers},
    tabsize=4,
    captionpos=b,
    frame=L
}

\\begin{document}

\\section{Plagiarism matches}`;
            const endListingRegex = new RegExp('\\\\end{lstlisting}', 'g');
            const underscore = new RegExp('_', 'g');


            const contents = Object.keys(matches.reduce((accum, match) => {
                accum[match.files[0].id] = true;
                accum[match.files[1].id] = true;
                return accum;
            }, {})).reduce((accum, fileId) => {
                accum[fileId] = this.$http.get(`/api/v1/code/${fileId}`).then(
                    a => a.data.split('\n').map(l => l.replace(endListingRegex, '\\end {lstlisting}')),
                );
                return accum;
            }, {});

            let i = 0;
            const middle = await Promise.all(matches.map(async (match) => {
                const left = (await contents[match.files[0].id]).slice(
                    match.lines[0][0], match.lines[0][1],
                );
                const right = (await contents[match.files[1].id]).slice(
                    match.lines[1][0], match.lines[1][1],
                );
                i += 1;
                return `\\subsection*{Match ${i}}
    \\begin{lstlisting}[firstnumber=${match.lines[0][0] + 1}, caption={File \\texttt{${this.getFromFileTree(this.tree1, match.files[0]).replace(underscore, '\\_')}} of ${this.detail.users[0].name}}]
${left.join('\n')}
    \\end{lstlisting}
    \\begin{lstlisting}[firstnumber=${match.lines[1][0] + 1}, caption={File \\texttt{${this.getFromFileTree(this.tree2, match.files[1]).replace(underscore, '\\_')}} of ${this.detail.users[1].name}}]
${right.join('\n')}
    \\end{lstlisting}`;
            }));

            const footer = '\\end{document}\n';

            return `${header}\n${middle.join('\n\n')}\n${footer}`;
        },

        updateSortedFiles() {
            const filesObj = this.detail.matches.reduce(
                (accum, match) => {
                    if (accum[match.files[0].id]) {
                        accum[match.files[0].id].lines.push(match.lines[0]);
                    } else {
                        accum[match.files[0].id] = {
                            name: match.files[0].name,
                            id: match.files[0].id,
                            lines: [match.lines[0]],
                        };
                    }
                    if (accum[match.files[1].id]) {
                        accum[match.files[1].id].lines.push(match.lines[1]);
                    } else {
                        accum[match.files[1].id] = {
                            name: match.files[1].name,
                            id: match.files[1].id,
                            lines: [match.lines[1]],
                        };
                    }

                    return accum;
                },
                {},
            );
            this.sortedFiles = Object.values(filesObj).sort((a, b) => {
                const lenA = a.lines.reduce((accum, item) => accum + (item[1] - item[0]), 0);
                const lenB = b.lines.reduce((accum, item) => accum + (item[1] - item[0]), 0);
                return lenA - lenB;
            });
            this.sortedFilesObject = filesObj;
        },


        async getFileContents() {
            this.contentLoaded = false;

            this.updateSortedFiles();

            await Promise.all(this.sortedFiles.map(async (file) => {
                const content = (await this.$http.get(`/api/v1/code/${file.id}`)).data;

                file.content = content.split('\n').map(this.$htmlEscape);
            }));

            this.highlightAllLines();
            this.contentLoaded = true;
        },

        highlightAllLines() {
            let colorIndex = 0;
            this.detail.matches.forEach((match) => {
                this.sortedFilesObject[match.files[0].id].content = this.highlightLines(
                    this.sortedFilesObject[match.files[0].id].content,
                    match,
                    match.lines[0],
                    colorIndex,
                );
                this.sortedFilesObject[match.files[1].id].content = this.highlightLines(
                    this.sortedFilesObject[match.files[1].id].content,
                    match,
                    match.lines[1],
                    colorIndex,
                );
                colorIndex += 1;
            });
        },

        highlightLines(lines, match, range, totalColorIndex) {
            const colorPair = this.colorPairs[totalColorIndex % this.colorPairs.length];

            for (let i = range[0]; i <= range[1]; i++) {
                lines[i] = { old: lines[i].old == null ? lines[i] : lines[i].old };
                lines[i].colored = `<span style="color: rgb(${colorPair.textColor}); background: rgba(${colorPair.background}, .1);">${lines[i].old}</span>`;
            }
            match.color = colorPair.background;

            return lines;
        },

        fileRoute(file, index) {
            return {
                name: 'submission_file',
                params: {
                    courseId: this.detail.assignments[index].course.id,
                    assignmentId: this.detail.assignments[index].id,
                    submissionId: this.detail.submissions[index].id,
                    fileId: file.id,
                },
            };
        },

        gotoLines(lines, files) {
            this.gotoLineInTarget(lines[0], files[0], 'self');
            this.gotoLineInTarget(lines[1], files[1], 'other');
        },

        // target must be 'self' or 'other'.
        gotoLineInTarget(lines, file, target) {
            const ref = `file-comparison-${target}`;
            const codeViewer = this.$refs[`${ref}-${this.getFromFileTree(target === 'self' ? this.tree1 : this.tree2, file)}`][0];

            const line = lines[0];

            codeViewer.querySelectorAll('li')[Math.max(line - 1, 0)].scrollIntoView();
            codeViewer.parentNode.scrollTop -= codeViewer.querySelector('.card-header').clientHeight;
        },

        loadDetail() {
            this.loadingData = true;

            this.$http.get(
                `/api/v1/plagiarism/${this.plagiarismRunId}/cases/${this.plagiarismCaseId}`,
            ).then(
                ({ data }) => {
                    if (data.assignments[0].id !== this.assignmentId) {
                        data.users.reverse();
                        data.assignments.reverse();
                        data.submissions.reverse();

                        for (let i = 0, l = data.matches.length; i < l; i++) {
                            const match = data.matches[i];
                            match.files.reverse();
                            match.lines.reverse();
                        }
                    }

                    this.detail = data;

                    return Promise.all([
                        this.loadCourses(),
                        this.loadFileTrees(),
                        this.getFileContents(),
                    ]);
                },
                (err) => {
                    this.error = err.response.data.message;
                    if (err.response.status === 403) {
                        this.error += ' Make sure you have the `can_view_plagiarism` on both courses where the submissions originate.';
                    }
                },
            ).then(
                () => { this.loadingData = false; },
            );
        },

        async loadFileTrees() {
            [this.tree1, this.tree2] = await Promise.all([
                this.$http.get(
                    `/api/v1/submissions/${this.detail.submissions[0].id}/files/`,
                ).then(a => this.processFileTree(a.data)).catch(() => null),
                this.$http.get(
                    `/api/v1/submissions/${this.detail.submissions[1].id}/files/`,
                ).then(a => this.processFileTree(a.data)).catch(() => null),
            ]);
        },

        getFromFileTree(tree, file) {
            const out = tree ? tree[file.id] : file.name;
            return out || file.name;
        },

        processFileTree(tree, base = '') {
            const newBase = base ? `${base}/${tree.name}` : tree.name;
            if (tree.entries) {
                return tree.entries.reduce(
                    (accum, e) => Object.assign(accum, this.processFileTree(e, newBase)),
                    {},
                );
            } else {
                return { [tree.id]: newBase };
            }
        },

        exportToLatex() {
            const btn = this.$refs.submitExport;
            const matches = this.detail.matches.filter(a => this.exportMatches[a.id]);
            if (matches.length === 0) {
                btn.fail('Select at least one case.');
                return;
            }
            btn.submit(this.getTexFile(
                matches,
            ).then((text) => {
                this.$http.post('/api/v1/files/', text).then((response) => {
                    this.exportMatches = {};
                    const fileName = `plagiarism_case_${this.detail.users[0].name}+${this.detail.users[1].name}.tex`;
                    window.open(`/api/v1/files/${response.data}/${encodeURIComponent(fileName)}`, '_blank');
                });
            }));
        },
    },

    mounted() {
        this.loadDetail();
    },

    components: {
        Icon,
        Loader,
        LocalHeader,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.plagiarism-detail {
    display: flex;
    flex-direction: column;
    height: 80vh;
    margin-bottom: 0 !important;
}

.local-header {
    flex: 0 0 auto;
}

.range-table-wrapper {
    max-height: 8em;
    flex: 0 0 auto;
    overflow-y: auto;
    border: 1px solid rgba(0, 0, 0, .125);
    border-radius: .25rem;
}

.range-table {
    margin-bottom: 0;

    .col-student-name,
    .col-student-name {
        width: 50%;
    }

    .col-student-range,
    .col-student-range {
        width: 1px;
        white-space: nowrap;
        text-align: center;
    }

    th,
    td {
        border-top: none;
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
}

.code-viewer {
    margin-top: .75rem;
    flex: 4 4 auto;
    overflow-y: auto;
}

.code-viewer {
    display: flex;
    flex-direction: row;
    padding: 0;
    margin-bottom: 1rem;
}

.student-files {
    flex: 0 0 50%;
    max-height: 100vh;
    overflow: auto;
    position: relative;
}

.student-file {
    margin-top: 0 !important;
    border-left: 0;
    border-right: 0;
    border-top: 0;

    &:last-child {
        border-bottom: 0;
    }

    &:not(:first-child) {
        margin-top: -1px;
        border-top-left-radius: 0;
        border-top-right-radius: 0;
    }

    &:not(:last-child) {
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }

    .student-files:not(:first-child) & {
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
    }

    .student-files:not(:last-child) & {
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }

    .card-header {
        position: sticky;
        top: 0;
        z-index: 5;
        background-color: @linum-bg;
        margin-bottom: -1px;

        .link-disabled {
            color: @color-secondary-text-lighter !important;
        }
    }
}

ol {
    min-height: 5em;
    margin: 0;
    padding-top: 0 !important;
    padding-right: 0 !important;
    padding-bottom: 0 !important;
    background: @linum-bg;
    font-family: monospace;
    font-size: small;

    #app.dark & {
        background: @color-primary-darkest;
        color: @color-secondary-text-lighter;
    }

    &:not(:last-child) {
        border-right: 1px solid @color-light-gray;
    }
}

li {
    position: relative;
    padding-left: .75em;
    padding-right: .75em;

    background-color: lighten(@linum-bg, 1%);
    border-left: 1px solid darken(@linum-bg, 5%);

    #app.dark & {
        background: @color-primary-darker;
        border-left: 1px solid darken(@color-primary-darkest, 5%);
    }
}

code {
    border-bottom: 1px solid transparent;
    color: @color-secondary-text;
    white-space: pre-wrap;

    word-wrap: break-word;
    word-break: break-word;
    -ms-word-break: break-all;

    -webkit-hyphens: auto;
    -moz-hyphens: auto;
    -ms-hyphens: auto;
    hyphens: auto;

    #app.dark & {
        color: #839496;
    }
}

.title {
    margin-bottom: 0;
    margin-left: 15px;
    flex: 1 1 auto;
}

.plagiarism-detail .input-group-prepend {
    margin-top: 0;
}

</style>

<style lang="less">
@export-modal-width: 75vw;
@export-modal-margin: (100vw - @export-modal-width) / 2;

#plagiarism-export .modal-dialog {
    max-width: @export-modal-width;
    margin-left: @export-modal-margin;
    margin-right: @export-modal-margin;

    .modal-content {
        width: @export-modal-width;
    }
}
</style>
