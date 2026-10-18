// Run with playwright-cli run-code --filename=frontend/tests/navigation.browser.mjs.
async (page) => {
  await page.goto('http://localhost:5173/does-not-exist');
  await page.getByRole('heading', { name: 'Your messages already know what needs to be done.' }).waitFor();
  if (new URL(page.url()).pathname !== '/') throw new Error('Unknown route did not redirect home');
  return 'Unknown route renders the landing page';
}
