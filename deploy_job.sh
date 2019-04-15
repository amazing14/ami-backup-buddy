#!/usr/bin/env bash

#
#  D E P L O Y _ J O B . S H
#
#  Tasks:
#  - Set IAM role and policy for lambda functions (AWS global)
#  - Upload lambda functions + their configs (per AWS region)
#  - Schedule runs for functions (per function interval, per AWS region)
#
#  Note:
#  - Lambda functions are region-specific, pushing job to us-east-1
#

#  Constants
AWS_LAMBDA_DESC="Backup Buddy"
AWS_LAMBDA_ROLE="backup-buddy-lambda-role"
AWS_LAMBDA_POLICY="manage-backup-buddy"
AWS_REGIONS=(
    'us-east-1'
)

ADDTL_ZIP_FILES="ami_shared.py"                         #  Include these file(s) in zip
ADDTL_ZIP_FOLDERS=""                                    #  Include these folder(s) in zip

#  Function monikers match file names (no extension)
FUNCTION_INFO=(
    'ami-create-backups:4 hours'                        #  "Name of .py file" : "How often to run"
    'ami-prune-backups:6 hours'                         #  "Name of .py file" : "How often to run"
    'ami-monitor-backups:1 day'                         #  "Name of .py file" : "How often to run"
)

DELETE_FILES=(
    '*.pyc'
    '.DS_Store'
)

#  Lambda settings (memory in MB, timeout in secs)
LAMBDA_MEMORY=128
LAMBDA_TIMEOUT=300


#  Usage
usage() {
    echo "Usage: ${0##*/} --all | --iam | --lambda | --schedule" 1>&2
    echo ""
    echo "Note:" 1>&2
    echo "--all      : deploy ALL components" 1>&2
    echo "--iam      : deploy ONLY IAM role and policy for lambda function(s)" 1>&2
    echo "--lambda   : deploy ONLY lambda function(s)" 1>&2
    echo "--schedule : deploy ONLY scheduled events for lambda function(s)" 1>&2
    exit 1
}


#  IAM ROLE + POLICY
iam () {
    echo "IAM: Tasks [BEGIN]"

    #  Check if role exists
    role_err_code=$(aws iam get-role --role-name ${AWS_LAMBDA_ROLE} --output text > /dev/null 2>&1; echo $?)
    if [[ "${role_err_code}" -eq 0 ]]; then
        #  Role already exists, update assume-role-policy
        echo "IAM: Role [${AWS_LAMBDA_ROLE}] already exists, update assume-role-policy"
        x=$(aws iam update-assume-role-policy                           \
                --role-name ${AWS_LAMBDA_ROLE}                          \
                --policy-document file://iam-trust.json                 \
                --output text                                           \
        )
    else
        #  Create new role
        echo "IAM: Creating [${AWS_LAMBDA_ROLE}] role with new assume-role-policy"
        x=$(aws iam create-role                                         \
                --role-name ${AWS_LAMBDA_ROLE}                          \
                --assume-role-policy-document file://iam-trust.json     \
                --output text                                           \
        )
    fi

    #  Add or update policy
    echo "IAM: Updating [${AWS_LAMBDA_ROLE}] role with [${AWS_LAMBDA_POLICY}] role-policy"
    x=$(aws iam put-role-policy                                         \
                --role-name ${AWS_LAMBDA_ROLE}                          \
                --policy-name ${AWS_LAMBDA_POLICY}                      \
                --policy-document file://iam-policy.json                \
                --output text                                           \
    )
    echo "IAM: Tasks [END]"
    echo ""
}


#  LAMBDA FUNCTIONS
lambda () {
    echo "LAMBDA: Tasks [BEGIN]"

    #  Remove
    echo "LAMBDA: Removing extraneous file(s)"
    for delfiles in "${DELETE_FILES[@]}"; do
        find . -name "${delfiles}" -type f -delete
    done

    #  Get the ARN Identifier for AWS_LAMBDA_ROLE (Global)
    role_arn=$(aws iam get-role --role-name ${AWS_LAMBDA_ROLE} --query "Role.Arn" --output text)

    #  Loop thru lambda functions
    for key in "${FUNCTION_INFO[@]}"; do
        function_name=$(echo ${key} | cut -d':' -f1)

        #  Package python script unto zip file
        echo "LAMBDA: Zipping [${function_name}] file"
        [[ -f ${function_name}.zip ]] && rm -rf ${function_name}.zip
        zip --recurse-paths --quiet ${function_name}.zip ${function_name}.py ${ADDTL_ZIP_FILES} ${ADDTL_ZIP_FOLDERS}

        #  Loop thru regions
        for region in "${AWS_REGIONS[@]}"; do
            #  Check if function already exists (per region)
            func_err_code=$(aws lambda get-function --function-name ${function_name} --region ${region} > /dev/null 2>&1; echo $?)
            if [[ "${func_err_code}" -eq 0 ]]; then
                echo "LAMBDA: Updating [${function_name}] function in [${region}]"

                #  Update function config (per region)
                x=$(aws lambda update-function-configuration              \
                        --function-name ${function_name}                  \
                        --description "${AWS_LAMBDA_DESC}"                \
                        --runtime python2.7                               \
                        --role ${role_arn}                                \
                        --handler ${function_name}.lambda_handler         \
                        --memory-size ${LAMBDA_MEMORY}                    \
                        --timeout ${LAMBDA_TIMEOUT}                       \
                        --region ${region}                                \
                )

                #  Update function code (per region)
                y=$(aws lambda update-function-code                       \
                        --function-name ${function_name}                  \
                        --zip-file fileb://${function_name}.zip           \
                        --region ${region}                                \
                )
            else
                #  Create brand new function (per region)
                echo "LAMBDA: Creating [${function_name}] function in [${region}]"
                x=$(aws lambda create-function                            \
                        --function-name ${function_name}                  \
                        --description "${AWS_LAMBDA_DESC}"                \
                        --runtime python2.7                               \
                        --role ${role_arn}                                \
                        --handler ${function_name}.lambda_handler         \
                        --memory-size ${LAMBDA_MEMORY}                    \
                        --timeout ${LAMBDA_TIMEOUT}                       \
                        --zip-file fileb://${function_name}.zip           \
                        --region ${region}                                \
                )
            fi
        done

        #  Remove zip file
        echo "LAMBDA: Removing [${function_name}] zip file"
        [[ -f ${function_name}.zip ]] && rm -rf ${function_name}.zip
    done
    echo "LAMBDA: Tasks [END]"
    echo ""
}


#  EVENT SCHEDULING
schedule () {
    echo "SCHEDULE: Tasks [BEGIN]"

    #  Loop thru lambda functions
    for key1 in "${FUNCTION_INFO[@]}"; do
        function_name=$(echo ${key1} | cut -d':' -f1)

        #  Loop thru regions
        for region in "${AWS_REGIONS[@]}"; do
            #  Get ARN Identifier for function to be scheduled (per region)
            function_arn=$(aws lambda get-function                          \
                                --function-name ${function_name}            \
                                --region ${region}                          \
                                --query "Configuration.FunctionArn"         \
                                --output text                               \
            )

            #  Get function's policy, will list all lambda permissions (per region)
            function_policy_json=$(aws lambda get-policy                    \
                                --function-name ${function_name}            \
                                --query "Policy"                            \
                                --region ${region}                          \
                                --output text                               \
                                2>/dev/null
            )

            #  Loop thru scheduled intervals
            for key in "${FUNCTION_INFO[@]}"; do
                func_name=$(echo ${key} | cut -d':' -f1)
                interval=$( echo ${key} | cut -d':' -f2)

                #  Use sanitized interval for rule name
                interval_title=$(echo ${interval} | gsed -e 's/[^a-zA-Z0-9]/\-/g')

                #  If current function matches current function-interval
                if [[ "${func_name}" == "${function_name}" ]]; then
                    #  Set (create or update) rule per interval (per region)
                    echo "SCHEDULE: Setting rule for [${function_name} @ ${interval_title}] function in [${region}]"
                    rule_arn=$(aws events put-rule                                                  \
                                    --name ${function_name}-schedule-${interval_title}              \
                                    --schedule-expression "rate(${interval})"                       \
                                    --region ${region}                                              \
                                    --output text                                                   \
                    )

                    #  Set (create or update) rule target per interval (per region)
                    echo "SCHEDULE: Setting target for [${function_name} @ ${interval}] function in [${region}]"
                    x=$(aws events put-targets                                                                                  \
                            --rule ${function_name}-schedule-${interval_title}                                                  \
                            --targets "Id=${function_name},Arn=${function_arn},Input='{ \"interval\": \"${interval}\"  }'"      \
                            --region ${region}                                                                                  \
                    )

                    #  Check if function permission already exists
                    chk_func_perm=$(echo $function_policy_json | jq '.Statement[] | select(.Sid=="'${function_name}'-schedule-'${interval_title}'-rule")')
                    if [[ -z "${chk_func_perm}" ]]; then
                        #  Grant rule permission to invoke lambda function per interval (per region)
                        #
                        #  Note: "statement-id" is the permission's unique identifier - use it when removing it via "lambda remove-permission" call
                        echo "SCHEDULE: Granting rule permission to invoke [${function_name} @ ${interval}] function in [${region}]"
                        y=$(aws lambda add-permission                                               \
                                --function-name ${function_name}                                    \
                                --statement-id ${function_name}-schedule-${interval_title}-rule     \
                                --action 'lambda:InvokeFunction'                                    \
                                --principal events.amazonaws.com                                    \
                                --source-arn ${rule_arn}                                            \
                                --region ${region}                                                  \
                        )
                    else
                        echo "SCHEDULE: Rule has already permission to invoke [${function_name} @ ${interval}] function in [${region}]"
                    fi
                fi
            done
        done
    done
    echo "SCHEDULE: Tasks [END]"
    echo ""
}


# Installation flags
FG_ALL=false; FG_IAM=false; FG_LAMBDA=false; FG_SCHEDULE=false

#  Determine flags enabled via parameters
if [[ -z "$@" ]]; then
    usage
else
    for arg in "$@"; do
        shift
        case "$arg" in
            --all)      FG_ALL=true ;;                  #  Deploy everything!
            --iam)      FG_IAM=true ;;
            --lambda)   FG_LAMBDA=true ;;
            --schedule) FG_SCHEDULE=true ;;
            *)          usage ;;
        esac
    done
fi

#  Call Sub-routines depending on paramater flag
[[ "$FG_ALL" == true || "$FG_IAM" == true ]]      && iam
[[ "$FG_ALL" == true || "$FG_LAMBDA" == true ]]   && lambda
[[ "$FG_ALL" == true || "$FG_SCHEDULE" == true ]] && schedule
