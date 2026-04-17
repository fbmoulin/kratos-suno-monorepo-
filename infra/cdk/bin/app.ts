#!/usr/bin/env node
/**
 * CDK entry point. Uso:
 *   pnpm cdk:deploy:staging
 *   pnpm cdk:deploy:prod
 *
 * Precisa de env vars:
 *   CDK_DEFAULT_ACCOUNT=123456789012
 *   CDK_DEFAULT_REGION=us-east-1
 *   ALERT_EMAIL=felipe@example.com
 *
 * Primeira vez:
 *   npx cdk bootstrap aws://ACCOUNT/REGION
 */

import "source-map-support/register";
import * as cdk from "aws-cdk-lib";

import { getConfig } from "../lib/config/environments";
import { getStandardTags } from "../lib/config/tags";
import { BackendStack } from "../lib/stacks/backend-stack";
import { CicdStack } from "../lib/stacks/cicd-stack";

const app = new cdk.App();

const envName = app.node.tryGetContext("env") ?? "staging";
const config = getConfig(envName);
const alertEmail = process.env.ALERT_EMAIL ?? "felipe@example.com";

// Aplica tags globais antes de criar stacks
const tags = getStandardTags(envName);
Object.entries(tags).forEach(([k, v]) => {
  cdk.Tags.of(app).add(k, v);
});

// Backend: App Runner + Secrets + Alarms + Budget
const backend = new BackendStack(app, `kratos-suno-backend-${envName}`, {
  env: config.awsEnv,
  config,
  alertEmail,
  description: `Kratos Suno backend (${envName}) — App Runner + Secrets Manager + CloudWatch`,
});

// CICD: OIDC + role para GitHub Actions
new CicdStack(app, `kratos-suno-cicd-${envName}`, {
  env: config.awsEnv,
  config,
  ecrRepositoryArn: backend.ecrRepositoryArn,
  appRunnerServiceArn: backend.serviceArn,
  description: `Kratos Suno CI/CD (${envName}) — GitHub Actions OIDC + deploy role`,
});

app.synth();
