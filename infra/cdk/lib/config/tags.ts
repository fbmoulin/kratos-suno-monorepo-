/**
 * Tags padrão aplicadas a todos os recursos — exigido pela skill aws-deploy
 * e crítico para atribuição de custo no Cost Explorer.
 */
export interface StandardTags {
  project: string;
  environment: string;
  owner: string;
  "cost-center": string;
  "managed-by": string;
}

export function getStandardTags(environment: string): StandardTags {
  return {
    project: "kratos-suno-prompt",
    environment,
    owner: "felipe-moulin",
    "cost-center": "lex-intelligentia",
    "managed-by": "cdk",
  };
}
