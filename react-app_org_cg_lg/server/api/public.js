const express = require('express');
const fs = require('fs');
const path = require('path');
// const Book = require('../models/Book'); // Commented out for mocking
// const Chapter = require('../models/Chapter'); // Commented out for mocking

const router = express.Router();

router.get('/books', async (req, res) => {
  // try { // Commented out for mocking
  //   const books = await Book.list(); // Commented out for mocking
  //   res.json(books);
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
      githubLastCommitSha: 'mocksha1',
    },
  ]);
});

router.get('/books/:slug', async (req, res) => {
  // try { // Commented out for mocking
  //   const book = await Book.getBySlug({ slug: req.params.slug }); // Commented out for mocking
  //   res.json(book);
  // } catch (err) {
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    _id: 'mockbook1',
    name: 'Mock Book 1',
    slug: req.params.slug,
    price: 10,
    createdAt: new Date(),
    githubRepo: 'mock/repo1',
    githubLastCommitSha: 'mocksha1',
    chapters: [
      {
        _id: 'mockchapter1',
        title: 'Mock Chapter 1',
        slug: 'mock-chapter-1',
        isFree: true,
        order: 1,
      },
    ],
  });
});

router.get('/get-chapter-detail', async (req, res) => {
  // try { // Commented out for mocking
  //   const { bookSlug, chapterSlug } = req.query;
  //   const chapter = await Chapter.getBySlug({ // Commented out for mocking
  //     bookSlug,
  //     chapterSlug,
  //     userId: req.user && req.user.id,
  //     isAdmin: req.user && req.user.isAdmin,
  //   });
  //   res.json(chapter);
  // } catch (err) {
  //   res.json({ error: err.message || err.toString() });
  // }
  // Mock data:
  res.json({
    _id: 'mockchapter1',
    title: 'Mock Chapter 1',
    slug: req.query.chapterSlug,
    htmlContent: '<p>This is mock chapter content.</p>',
    isFree: true,
    order: 1,
    book: {
      _id: 'mockbook1',
      name: 'Mock Book 1',
      slug: req.query.bookSlug,
      chapters: [
        {
          _id: 'mockintrochapter',
          title: 'Introduction',
          slug: 'introduction',
          order: 0,
        },
        {
          _id: 'mockchapter1',
          title: 'Mock Chapter 1',
          slug: 'mock-chapter-1',
          order: 1,
        },
        {
          _id: 'mockchapter2',
          title: 'Mock Chapter 2',
          slug: 'mock-chapter-2',
          order: 2,
        },
      ],
    },
  });
});

// New endpoint to get available language folders
router.get('/languages', async (req, res) => {
  try {
    const localesPath = path.join(process.cwd(), 'public', 'locales');
    
    // Check if the locales directory exists
    if (!fs.existsSync(localesPath)) {
      return res.status(404).json({ error: 'Locales directory not found' });
    }

    // Read all items in the locales directory
    const items = fs.readdirSync(localesPath);
    
    // Filter only directories (language folders)
    const languageFolders = items.filter(item => {
      const itemPath = path.join(localesPath, item);
      return fs.statSync(itemPath).isDirectory();
    });

    res.json(languageFolders);
  } catch (error) {
    console.error('Error reading language folders:', error);
    res.status(500).json({ error: 'Failed to read language folders' });
  }
});

module.exports = router;