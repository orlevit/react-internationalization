const express = require('express');
// const Book = require('../models/Book'); // Commented out for mocking
// const Purchase = require('../models/Purchase'); // Commented out for mocking
const { createSession } = require('../stripe');
const logger = require('../logger');

const router = express.Router();

router.use((req, res, next) => {
  // Mock user for testing when DB is down
  if (!req.user) {
    req.user = {
      _id: 'mockuserid',
      email: 'mock@user.com',
      purchasedBookIds: ['mockbook1'],
      isAdmin: false,
    };
    // res.status(401).json({ error: 'Unauthorized' }); // Original check
    // return;
  }

  next();
});

router.post('/stripe/fetch-checkout-session', async (req, res) => {
  try {
    const { bookId, redirectUrl } = req.body;

    // const book = await Book.findById(bookId).select(['slug']).setOptions({ lean: true }); // Commented out for mocking
    // Mock book data
    const mockBook = { _id: bookId, slug: 'mock-book-slug' };

    // if (!book) { // Commented out for mocking
    //   throw new Error('Book not found');
    // }

    // const isPurchased = // Commented out for mocking
    //   (await Purchase.find({ userId: req.user._id, bookId: book._id }).countDocuments()) > 0;
    // Mock purchase check (assume not purchased)
    const isPurchased = false;

    if (isPurchased) {
      throw new Error('You already bought this book.');
    }

    const session = await createSession({
      userId: req.user._id.toString(),
      userEmail: req.user.email,
      bookId,
      bookSlug: mockBook.slug, // Use mock book slug
      redirectUrl,
    });

    // Mock Stripe session ID if createSession fails or needs mocking
    const sessionId = session ? session.id : 'mock_session_id';

    res.json({ sessionId });
  } catch (err) {
    logger.error(err);
    // Provide a mock session ID even on error during mocking
    res.json({ sessionId: 'mock_session_id_on_error', error: err.message || err.toString() });
  }
});

router.get('/my-books', async (req, res) => {
  // try { // Commented out for mocking
  const { purchasedBookIds = [] } = req.user;

  // const purchasedBooks = await Book.getPurchasedBooks({ purchasedBookIds }); // Commented out for mocking
  // Mock purchased books data
  const purchasedBooks = purchasedBookIds.map((id) => ({
    _id: id,
    name: `Mock Book ${id}`,
    slug: `mock-book-${id}`,
    price: 15,
    createdAt: new Date(),
  }));

  res.json({ purchasedBooks });
  // } catch (err) { // Commented out for mocking
  //   res.json({ error: err.message || err.toString() });
  // }
});

module.exports = router;
