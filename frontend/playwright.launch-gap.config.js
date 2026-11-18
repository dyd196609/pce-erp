import { defineConfig } from '@playwright/test'
export default defineConfig({
 testDir:'./tests/ui-baseline',testMatch:'emptyTableFixedHeaderStability.spec.js',workers:1,timeout:60000,
 outputDir:'test-results/launch-gap-layout',reporter:[['line']],
 use:{baseURL:'http://127.0.0.1:57324',channel:'chrome',headless:true,screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:{command:'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 57324 --strictPort',url:'http://127.0.0.1:57324',reuseExistingServer:false,timeout:60000}
})

