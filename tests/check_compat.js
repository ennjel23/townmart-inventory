// Flags syntax/APIs newer than ~Chrome 61 (old Android WebView) in the page's inline script and CSS.
// Usage: npm install typescript && node tests/check_compat.js app/src/main/assets/index.html
const ts=require('typescript');const fs=require('fs');
const html=fs.readFileSync(process.argv[2],'utf8');
const js=html.slice(html.lastIndexOf('<script>')+8,html.lastIndexOf('</script>'));
const css=html.slice(html.indexOf('<style>'),html.indexOf('</style>'));
const sf=ts.createSourceFile('a.js',js,ts.ScriptTarget.Latest,true);const bad=[];
const K=ts.SyntaxKind;
function walk(n){
  if(n.kind===K.QuestionQuestionToken)bad.push('?? nullish');
  if(n.questionDotToken)bad.push('?. optional chaining');
  if(n.kind===K.PropertyAccessExpression){const nm=n.name.text;if(['at','replaceAll','flat','flatMap','fromEntries','matchAll','allSettled','structuredClone','toggleAttribute','findLast'].includes(nm))bad.push('API .'+nm);}
  if(n.kind===K.Identifier&&['structuredClone','globalThis'].includes(n.text))bad.push('API '+n.text);
  if(n.kind===K.BigIntLiteral)bad.push('bigint');
  if((n.kind===K.BinaryExpression)&&[K.QuestionQuestionEqualsToken,K.BarBarEqualsToken,K.AmpersandAmpersandEqualsToken].includes(n.operatorToken.kind))bad.push('logical assignment');
  if(n.kind===K.PropertyDeclaration)bad.push('class field');
  if(n.kind===K.CatchClause&&!n.variableDeclaration)bad.push('optional catch binding');
  ts.forEachChild(n,walk)}
walk(sf);
const diag=sf.parseDiagnostics||[];if(diag.length)bad.push('PARSE ERRORS: '+diag.map(d=>d.messageText).join('; '));
for(const [f,re] of [['light-dark',/light-dark\(/],['color-mix',/color-mix\(/],[':has',/:has\(/],['inset',/[;{]inset:/],['aspect-ratio',/aspect-ratio/],['clamp',/clamp\(/],['min()',/[^x-]min\(/],['max()',/[^n-]max\(/],['@container',/@container/],['dvh',/\ddvh/],['text-wrap',/text-wrap/],['flex gap',/[;{]gap:/]])if(re.test(css))bad.push('CSS '+f);
console.log(bad.length?'FOUND: '+[...new Set(bad)].join(', '):'clean');
