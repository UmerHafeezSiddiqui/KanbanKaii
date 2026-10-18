import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const outfile = '.test-build/regressions.test.mjs';
await build({
  entryPoints: ['tests/regressions.test.tsx'], outfile, bundle: true,
  platform: 'node', format: 'esm', packages: 'external', jsx: 'automatic',
  alias: { '@': path.resolve('src') },
  plugins: [{
    name: 'external-service-fixtures',
    setup(builder) {
      builder.onResolve({ filter: /^(?:@\/api\/client|\.\/client)$/ },
        () => ({ path: path.resolve('tests/services.mjs') }));
      builder.onResolve({ filter: /^lucide-react\/dist\// },
        (args) => ({ path: path.resolve('node_modules', `${args.path}.js`) }));
      builder.onResolve({ filter: /^(?:@\/(api\/(tickets|settings)|auth\/AuthContext|lib\/supabase)|\.\/AuthContext)$/ },
        () => ({ path: path.resolve('tests/services.mjs') }));
    },
  }],
});
const result = spawnSync(process.execPath, ['--test', '--import', './tests/setup.mjs', outfile], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
