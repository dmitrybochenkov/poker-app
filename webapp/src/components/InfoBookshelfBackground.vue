<template>
  <div class="info-library" aria-hidden="true">
    <div class="library-frame">
      <div v-for="(shelf, shelfIndex) in shelves" :key="`shelf-${shelfIndex}`" class="library-shelf">
        <div class="shelf-board shelf-board--top"></div>
        <div class="shelf-books">
          <div
            v-for="book in shelf.books"
            :key="book.title"
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
            <div class="trophy-cup">
              <span class="trophy-handle trophy-handle--left"></span>
              <span class="trophy-handle trophy-handle--right"></span>
              <div class="trophy-rim"></div>
              <div class="trophy-body"></div>
              <div class="trophy-stem"></div>
              <div class="trophy-base"></div>
            </div>
          </div>
        </div>
        <div class="shelf-board shelf-board--bottom"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
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
      { title: "DOYLE\nBRUNSON", suit: "♠", subtitle: "SUPER\nSYSTEM", width: "11%", tone: "ink" },
      { title: "PHIL\nIVEY", suit: "♣", subtitle: "READ\nPEOPLE", width: "10.5%", tone: "emerald" },
      { title: "CHRIS\nMONEYMAKER", suit: "♣", subtitle: "PLAY\nPOKER", width: "11%", tone: "emerald" },
      { title: "МЯКИН", suit: "♥", subtitle: "КУЛИНАРНЫЕ\nРЕЦЕПТЫ", width: "10%", tone: "wine" },
      { title: "JASON\nKOON", suit: "♦", subtitle: "THINKING\nPLAYER", width: "10%", tone: "wine" },
      { title: "ERIK\nSEIDEL", suit: "♠", subtitle: "SEIDEL\nON POKER", width: "10.5%", tone: "ink" },
      { title: "DANIEL\nNEGREANU", suit: "♦", subtitle: "POWER\nHOLD'EM", width: "10%", tone: "wine" },
      { title: "PHIL\nHELLMUTH", suit: "♥", subtitle: "HOW I WON\nTHE WSOP", width: "10%", tone: "emerald" },
      { title: "МАЯКИН", suit: "♦", subtitle: "Я БУХАЛ\nИ БУДУ", width: "10%", tone: "wine" },
      { title: "STU\nUNGAR", suit: "♣", subtitle: "ONE OF A\nKIND", width: "10%", tone: "ink" },
    ],
  },
  {
    books: [
      { title: "LINUS\nLOELIGER", suit: "♠", subtitle: "ELEMENTS\nOF POKER", width: "10%", tone: "emerald" },
      { title: "КУЗЬМИН", suit: "♣", subtitle: "КАК СТАВИТЬ\nИ ВЫИГРЫВАТЬ", width: "10.5%", tone: "wine" },
      { title: "JOHNNY\nMOSS", suit: "♣", subtitle: "THE GRAND\nOLD MAN", width: "10%", tone: "ink" },
      { title: "VIKTOR\n\"ISILDUR1\"\nBLOM", suit: "♠", subtitle: "ONLINE\nLEGEND", width: "10.5%", tone: "emerald" },
      { title: "ИЛЛАРИОНОВ", suit: "♦", subtitle: "ДРОЧИЛА", width: "10%", tone: "wine" },
      { title: "BERTRAND\nGROSPELLIER", suit: "♦", subtitle: "LIVE POKER\nSTRATEGY", width: "10%", tone: "emerald" },
      { title: "FEDOR\nHOLZ", suit: "♥", subtitle: "NO LIMIT\nHOLD'EM", width: "10%", tone: "wine" },
      { title: "MEN\nNGUYEN", suit: "♠", subtitle: "THE\nMASTER", width: "9.5%", tone: "ink" },
    ],
    trophy: true,
  },
  {
    books: [
      { title: "SAMMY\nFARHA", suit: "♠", subtitle: "POKER\nIS WAR", width: "10.5%", tone: "ink" },
      { title: "TONY G", suit: "♦", subtitle: "POKER\nBRAT", width: "10%", tone: "wine" },
      { title: "JUSTIN\nBONOMO", suit: "♠", subtitle: "THE POKER\nTHINKER", width: "10%", tone: "ink" },
      { title: "PATRICK\nANTONIUS", suit: "♥", subtitle: "RELENTLESS", width: "10%", tone: "wine" },
      { title: "NIK\nAIRBALL", suit: "♣", subtitle: "EXPLOIT\nTHE LIVE GAME", width: "10%", tone: "emerald" },
      { title: "BRYN\nKENNEY", suit: "♣", subtitle: "THE POKER\nTHINKER", width: "10%", tone: "emerald" },
      { title: "TOM\nDWAN", suit: "♣", subtitle: "THE\nLEGEND", width: "10%", tone: "ink" },
      { title: "LIV\nBOEREE", suit: "♦", subtitle: "LADY\nLEGEND", width: "10%", tone: "wine" },
      { title: "ROBBI\nJADE LEW", suit: "♣", subtitle: "THE\nWARRIOR", width: "10%", tone: "ink" },
    ],
  },
];
</script>
