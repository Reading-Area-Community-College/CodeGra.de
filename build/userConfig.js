/* SPDX-License-Identifier: AGPL-3.0-only */
const fs = require('fs');
const ini = require('ini');
const execFileSync = require('child_process').execFileSync;
const moment = require('moment');

let userConfig = {};

try {
    userConfig = ini.parse(fs.readFileSync('./config.ini', 'utf-8'));
} catch (err) {
    process.stderr.write('Config file not found, using default values!\n');
}

if (userConfig['Front-end'] === undefined) userConfig['Front-end'] = {};
if (userConfig.Features === undefined) userConfig.Features = {};

const config = Object.assign({}, {
    email: 'info@CodeGra.de',
}, userConfig['Front-end']);

const version = execFileSync('git', ['describe', '--abbrev=0', '--tags']).toString().trim();
const tagMsg = execFileSync('git', ['tag', '-l', '-n400', version]).toString().split('\n');
let inCorrectPart = false;
let done = false;
let skip = false;

config.release = {
    version,
    date: process.env.CG_FORCE_BUILD_DATE || moment.utc().toISOString(),
    message: tagMsg.reduce((res, cur) => {
        if (done || skip) {
            skip = false;
        } else if (inCorrectPart && /^ *$/.test(cur)) {
            done = true;
        } else if (inCorrectPart) {
            res.push(cur);
        } else if (/^ *\*\*Released\*\*/.test(cur)) {
            inCorrectPart = true;
            skip = true;
        }
        return res;
    }, []).join(' '),
};

config.features = Object.assign({}, {
    blackboard_zip_upload: true,
    rubrics: true,
    automatic_lti_role: true,
    LTI: true,
    linters: true,
    incremental_rubric_submission: true,
    register: false,
    groups: false,
}, userConfig.Features);

module.exports = config;
