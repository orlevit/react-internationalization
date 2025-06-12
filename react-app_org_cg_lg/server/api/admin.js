const express = require('express');
// const Book = require('../models/Book'); // Commented out for mocking
// const User = require('../models/User'); // Commented out for mocking
const { getRepos } = require('../github');
const logger = require('../logger');

const router = express.Router();

router.use((req, res, next) => {
  // Mock admin user for testing when DB is down
  if (!req.user) {
    req.user = {
      _id: 'mockadminid',
      id: 'mockadminid', // Ensure id is available if used directly
      email: 'mock@admin.com',
      purchasedBookIds: [],
      isAdmin: true,
      isGithubConnected: true, // Assume connected for mocking
      githubAccessToken: 'mock_token', // Assume token exists for mocking
    };
  }

  if (!req.user || !req.user.isAdmin) {
    // Keep the check but it will likely pass due to mock user
    res.status(401).json({ error: 'Unauthorized' });
    return;
  }

  next();
});

router.get('/books', async (req, res) => {
  // try { // Commented out for mocking
  //   const booksFromServer = await Book.list(); // Commented out for mocking
  //   res.json(booksFromServer);
  // } catch (err) {
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json([
    {
      _id: 'mockbook1',
      name: 'Mock Book 1',
      slug: 'mock-book-1',
      price: 10,
      createdAt: new Date(),
      githubRepo: 'mock/repo1',
    },
    {
      _id: 'mockbook2',
      name: 'Mock Book 2',
      slug: 'mock-book-2',
      price: 20,
      createdAt: new Date(),
      githubRepo: 'mock/repo2',
    },
  ]);
});

router.post('/books/add', async (req, res) => {
  // try { // Commented out for mocking
  //   const book = await Book.add({ userId: req.user.id, ...req.body }); // Commented out for mocking
  //   res.json(book);
  // } catch (err) { // Commented out for mocking
  //   logger.error(err);
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    _id: `mockbook${Date.now()}`,
    userId: req.user.id,
    createdAt: new Date(),
    ...req.body,
  });
});

router.post('/books/edit', async (req, res) => {
  // try { // Commented out for mocking
  //   const editedBook = await Book.edit(req.body); // Commented out for mocking
  //   res.json(editedBook);
  // } catch (err) { // Commented out for mocking
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    ...req.body, // Assume edit applies the body directly
    updatedAt: new Date(),
  });
});

router.get('/books/detail/:slug', async (req, res) => {
  // try { // Commented out for mocking
  //   const bookFromServer = await Book.getBySlug({ slug: req.params.slug }); // Commented out for mocking
  //   res.json(bookFromServer);
  // } catch (err) { // Comment out for mocking
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    _id: 'mockdetailbook',
    name: `Mock Detail Book: ${req.params.slug}`,
    slug: req.params.slug,
    price: 15,
    createdAt: new Date(),
    githubRepo: 'mock/detail-repo',
    chapters: [
      { _id: 'mockchapter1', title: 'Detail Chapter 1', slug: 'detail-chapter-1', order: 1 },
      { _id: 'mockchapter2', title: 'Detail Chapter 2', slug: 'detail-chapter-2', order: 2 },
    ],
  });
});

// github-related

router.get('/github/repos', async (req, res) => {
  // const user = await User.findById(req.user._id, 'isGithubConnected githubAccessToken'); // Commented out for mocking
  const user = req.user; // Use mocked user

  if (!user.isGithubConnected || !user.githubAccessToken) {
    res.json({ error: 'Github not connected' });
    return;
  }

  // try { // Commented out for mocking
  //   const response = await getRepos({ user, request: req });
  //   res.json({ repos: response.data });
  // } catch (err) {
  //   logger.error(err);
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    repos: [
      { id: 1, name: 'mock-repo-1', full_name: 'user/mock-repo-1', private: false },
      { id: 2, name: 'mock-repo-2', full_name: 'user/mock-repo-2', private: true },
    ],
  });
});

router.post('/books/sync-content', async (req, res) => {
  // const { bookId } = req.body; // Already have bookId from req.body

  // const user = await User.findById(req.user._id, 'isGithubConnected githubAccessToken'); // Commented out for mocking
  const user = req.user; // Use mocked user

  if (!user.isGithubConnected || !user.githubAccessToken) {
    res.json({ error: 'Github not connected' });
    return;
  }

  // try { // Commented out for mocking
  //   await Book.syncContent({ id: bookId, user, request: req }); // Commented out for mocking
  //   res.json({ done: 1 });
  // } catch (err) { // Commented out for mocking
  //   logger.error(err);
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  logger.info(`Mock sync content for bookId: ${req.body.bookId}`);
  res.json({ done: 1 });
});

module.exports = router;
