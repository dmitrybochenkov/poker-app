<template>
  <div class="info-library" aria-hidden="true">
    <div class="library-frame">
      <div class="library-top-cap"></div>
      <div
        v-for="(shelf, shelfIndex) in shelves"
        :key="`shelf-${shelfIndex}`"
        class="library-shelf"
        :class="{ 'library-shelf--first': shelfIndex === 0 }"
      >
        <template v-if="shelfIndex === 0">
        <div v-if="shelfIndex === 0" class="shelf-board shelf-board--top"></div>
        <div class="shelf-books">
          <div
            v-for="(book, bookIndex) in shelf.books"
            :key="`${shelfIndex}-${bookIndex}-${book.title}`"
            class="shelf-book"
            :class="`tone-${book.tone}`"
            :style="{ width: book.width }"
          >
            <div class="shelf-book-inner">
              <div class="shelf-book-title">{{ book.title }}</div>
              <div class="shelf-book-suit">{{ book.suit }}</div>
              <div class="shelf-book-subtitle">{{ book.subtitle }}</div>
            </div>
          </div>

          <div v-if="shelf.trophy" class="shelf-trophy">
            <img :src="trophySrc" alt="" class="trophy-image" />
          </div>
        </div>
        <div class="shelf-board shelf-board--bottom"></div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import trophySrc from "../assets/neofarm_trophy_clean.svg";

type BookTone = "ink" | "emerald" | "wine";

type Book = {
  title: string;
  suit: string;
  subtitle: string;
  width: string;
  tone: BookTone;
};

type Shelf = {
  books: Book[];
  trophy?: boolean;
};

const shelves: Shelf[] = [
  {
    books: [
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "🍾", subtitle: "Я БУХАЛ\nИ БУДУ\nБУХАТЬ", width: "18.5%", tone: "wine" },
      { title: "PHIL\nIVEY", suit: "♣", subtitle: "READ\nPEOPLE", width: "12.8%", tone: "emerald" },
      { title: "CHRIS\nMONEYMAKER", suit: "♣", subtitle: "PLAY\nPOKER", width: "18.8%", tone: "emerald" },
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "♥", subtitle: "КУЛИНАРНЫЕ\nРЕЦЕПТЫ", width: "19%", tone: "wine" },
      { title: "DANIEL\nNEGREANU", suit: "♦", subtitle: "POWER\nHOLD'EM", width: "17.8%", tone: "wine" },
      { title: "STU\nUNGAR", suit: "♣", subtitle: "ONE OF A\nKIND", width: "13.1%", tone: "ink" },
    ],
  },
  { books: [] },
  { books: [] },
];
</script>
