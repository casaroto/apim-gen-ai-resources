import express from "express";

const app = express();
app.use(express.json());

const books = [
  { id: 1, title: "The Pragmatic Programmer", author: "Hunt & Thomas" },
  { id: 2, title: "Designing Data-Intensive Applications", author: "Kleppmann" }
];
let nextId = 3;

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.get("/books", (_req, res) => res.json(books));

app.get("/books/:id", (req, res) => {
  const book = books.find(b => b.id === Number(req.params.id));
  if (!book) return res.status(404).json({ error: "not found" });
  res.json(book);
});

app.post("/books", (req, res) => {
  const { title, author } = req.body ?? {};
  if (!title || !author) return res.status(400).json({ error: "title and author required" });
  const book = { id: nextId++, title, author };
  books.push(book);
  res.status(201).json(book);
});

const port = Number(process.env.PORT ?? 3000);
app.listen(port, "0.0.0.0", () => {
  console.log(`backend listening on :${port}`);
});
