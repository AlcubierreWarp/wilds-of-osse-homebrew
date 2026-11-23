#!/bin/bash
# Deploys or updates the GUS relay on the "default" AWS profile in ca-central-1.
# First run creates the bucket, role, function, public address and both access keys.
# Later runs only update the function code. Pass --new-keys to replace both keys,
# --new-player-code to give the player a new short code (like ABCD-EFGH) that can be typed on the login screen
# (it also updates the code the table hub shows), or --new-dm-passcode for the hub's game master passcode
# (--set-dm-passcode reads a chosen one from standard input instead).
# The keys go to the macOS Keychain (services osse-gus-gm and osse-gus-player), never to a file.
set -euo pipefail
export AWS_PROFILE=default AWS_REGION=ca-central-1 AWS_PAGER=""
cd "$(dirname "$0")"

FN=osse-gus-relay
ROLE=osse-gus-relay
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="osse-gus-relay-$ACCOUNT"
ORIGINS='["https://alcubierrewarp.github.io","https://osse.thomashuet.ca","http://localhost:8713","http://localhost:8715"]'

if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint=$AWS_REGION >/dev/null
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi
aws s3api put-bucket-cors --bucket "$BUCKET" --cors-configuration \
  "{\"CORSRules\":[{\"AllowedOrigins\":$ORIGINS,\"AllowedMethods\":[\"PUT\",\"GET\"],\"AllowedHeaders\":[\"*\"],\"MaxAgeSeconds\":3600}]}"

make_key() {
  local name=$1 service=$2 key
  key=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  aws ssm put-parameter --name "/osse/gus/$name-key-sha256" --type SecureString --overwrite \
    --value "$(printf %s "$key" | shasum -a 256 | cut -d' ' -f1)" >/dev/null
  security add-generic-password -U -a osse -s "$service" -w "$key"
}
if [ "${1:-}" = "--new-player-code" ]; then
  code=$(python3 -c 'import secrets; a="ABCDEFGHJKMNPQRSTUVWXYZ23456789"; c="".join(secrets.choice(a) for _ in range(8)); print(c[:4]+"-"+c[4:])')
  aws ssm put-parameter --name /osse/gus/player-key-sha256 --type SecureString --overwrite \
    --value "$(printf %s "$code" | shasum -a 256 | cut -d' ' -f1)" >/dev/null
  security add-generic-password -U -a osse -s osse-gus-player -w "$code"
  printf '{"codes":{"gus":"%s"}}' "$code" | aws s3 cp - "s3://$BUCKET/hub.json" --content-type application/json >/dev/null
  aws lambda update-function-configuration --function-name osse-gus-relay \
    --environment "Variables={BUCKET=$BUCKET,KEYS_AT=$(date +%s)}" >/dev/null
  aws lambda wait function-updated-v2 --function-name osse-gus-relay
fi
if [ "${1:-}" = "--new-dm-passcode" ] || [ "${1:-}" = "--set-dm-passcode" ]; then
  if [ "$1" = "--set-dm-passcode" ]; then
    # Reads the passcode from standard input so it never lands in shell history or the repository.
    IFS= read -r code
    [ -n "$code" ] || { echo "No passcode given on standard input." >&2; exit 1; }
  else
    code=$(python3 -c 'import secrets; a="ABCDEFGHJKMNPQRSTUVWXYZ23456789"; c="".join(secrets.choice(a) for _ in range(8)); print(c[:4]+"-"+c[4:])')
  fi
  aws ssm put-parameter --name /osse/gus/dm-pass-sha256 --type SecureString --overwrite \
    --value "$(printf %s "$code" | shasum -a 256 | cut -d' ' -f1)" >/dev/null
  security add-generic-password -U -a osse -s osse-dm-passcode -w "$code"
  aws lambda update-function-configuration --function-name osse-gus-relay \
    --environment "Variables={BUCKET=$BUCKET,KEYS_AT=$(date +%s)}" >/dev/null
  aws lambda wait function-updated-v2 --function-name osse-gus-relay
fi
if [ "${1:-}" = "--new-keys" ] || ! aws ssm get-parameter --name /osse/gus/gm-key-sha256 >/dev/null 2>&1; then
  make_key gm osse-gus-gm
  make_key player osse-gus-player
fi

if ! aws iam get-role --role-name $ROLE >/dev/null 2>&1; then
  aws iam create-role --role-name $ROLE --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name $ROLE --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  sleep 10
fi
aws iam put-role-policy --role-name $ROLE --policy-name relay --policy-document "{
  \"Version\":\"2012-10-17\",\"Statement\":[
    {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\"],\"Resource\":\"arn:aws:s3:::$BUCKET/*\"},
    {\"Effect\":\"Allow\",\"Action\":\"s3:ListBucket\",\"Resource\":\"arn:aws:s3:::$BUCKET\"},
    {\"Effect\":\"Allow\",\"Action\":\"ssm:GetParameters\",\"Resource\":\"arn:aws:ssm:$AWS_REGION:$ACCOUNT:parameter/osse/gus/*\"}]}"

ZIP=$(mktemp -d)/relay.zip
zip -q -j "$ZIP" handler.py
if aws lambda get-function --function-name $FN >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $FN --zip-file "fileb://$ZIP" >/dev/null
else
  aws lambda create-function --function-name $FN --runtime python3.12 --architectures arm64 \
    --handler handler.handler --role "arn:aws:iam::$ACCOUNT:role/$ROLE" --timeout 10 --memory-size 256 \
    --environment "Variables={BUCKET=$BUCKET}" --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-active-v2 --function-name $FN
  aws lambda create-function-url-config --function-name $FN --auth-type NONE --cors \
    "{\"AllowOrigins\":$ORIGINS,\"AllowMethods\":[\"GET\",\"PUT\",\"POST\",\"DELETE\"],\"AllowHeaders\":[\"content-type\",\"x-gus-key\"],\"MaxAge\":3600}" >/dev/null
  aws lambda add-permission --function-name $FN --statement-id public-url --action lambda:InvokeFunctionUrl \
    --principal "*" --function-url-auth-type NONE >/dev/null
  aws lambda add-permission --function-name $FN --statement-id public-invoke --action lambda:InvokeFunction \
    --principal "*" --invoked-via-function-url >/dev/null
fi
aws lambda wait function-updated-v2 --function-name $FN
aws lambda update-function-url-config --function-name $FN --cors \
  "{\"AllowOrigins\":$ORIGINS,\"AllowMethods\":[\"GET\",\"PUT\",\"POST\",\"DELETE\"],\"AllowHeaders\":[\"content-type\",\"x-gus-key\"],\"MaxAge\":3600}" >/dev/null
aws lambda get-function-url-config --function-name $FN --query FunctionUrl --output text
