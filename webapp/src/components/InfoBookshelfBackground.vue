<template>
  <div class="info-library" aria-hidden="true">
    <div class="library-frame">
      <div v-for="(shelf, shelfIndex) in shelves" :key="`shelf-${shelfIndex}`" class="library-shelf">
        <div class="shelf-board shelf-board--top"></div>
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
      { title: "DOYLE\nBRUNSON", suit: "♠", subtitle: "SUPER\nSYSTEM", width: "11.8%", tone: "ink" },
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "🍾", subtitle: "Я БУХАЛ\nИ БУДУ\nБУХАТЬ", width: "13%", tone: "wine" },
      { title: "PHIL\nIVEY", suit: "♣", subtitle: "READ\nPEOPLE", width: "10.8%", tone: "emerald" },
      { title: "CHRIS\nMONEYMAKER", suit: "♣", subtitle: "PLAY\nPOKER", width: "13.2%", tone: "emerald" },
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "♥", subtitle: "КУЛИНАРНЫЕ\nРЕЦЕПТЫ", width: "13%", tone: "wine" },
      { title: "DANIEL\nNEGREANU", suit: "♦", subtitle: "POWER\nHOLD'EM", width: "12.6%", tone: "wine" },
      { title: "PHIL\nHELLMUTH", suit: "♥", subtitle: "HOW I WON\nTHE WSOP", width: "12.8%", tone: "emerald" },
      { title: "STU\nUNGAR", suit: "♣", subtitle: "ONE OF A\nKIND", width: "10.8%", tone: "ink" },
    ],
  },
  {
    books: [
      { title: "LINUS\nLOELIGER", suit: "♠", subtitle: "ELEMENTS\nOF POKER", width: "11.2%", tone: "emerald" },
      { title: "СЕРГЕЙ\nКУЗЬМИН", suit: "🤡", subtitle: "КАК СТАВИТЬ\nС ХУЙНЕЙ И\nВЫИГРЫВАТЬ!", width: "14.4%", tone: "wine" },
      { title: "JOHNNY\nMOSS", suit: "♣", subtitle: "THE GRAND\nOLD MAN", width: "11%", tone: "ink" },
      { title: "VIKTOR\n\"ISILDUR1\"\nBLOM", suit: "♠", subtitle: "ONLINE\nLEGEND", width: "13.4%", tone: "emerald" },
      { title: "АЛЕКСАНДР\nИЛЛАРИОНОВ", suit: "🍆", subtitle: "ДРОЧИЛА", width: "14.2%", tone: "wine" },
      { title: "BERTRAND\nGROSPELLIER", suit: "♦", subtitle: "LIVE POKER\nSTRATEGY", width: "13.6%", tone: "emerald" },
      { title: "FEDOR\nHOLZ", suit: "♥", subtitle: "NO LIMIT\nHOLD'EM", width: "11.2%", tone: "wine" },
    ],
    trophy: true,
  },
  {
    books: [
      { title: "SAMMY\nFARHA", suit: "♠", subtitle: "POKER\nIS WAR", width: "11.6%", tone: "ink" },
      { title: "TONY G", suit: "♦", subtitle: "POKER\nBRAT", width: "9.8%", tone: "wine" },
      { title: "JUSTIN\nBONOMO", suit: "♠", subtitle: "THE POKER\nTHINKER", width: "12.6%", tone: "ink" },
      { title: "PATRICK\nANTONIUS", suit: "♥", subtitle: "RELENTLESS", width: "12.4%", tone: "wine" },
      { title: "NIK\nAIRBALL", suit: "♣", subtitle: "EXPLOIT\nTHE LIVE GAME", width: "12.2%", tone: "emerald" },
      { title: "TOM\nDWAN", suit: "♣", subtitle: "THE\nLEGEND", width: "10.6%", tone: "ink" },
      { title: "LIV\nBOEREE", suit: "♦", subtitle: "LADY\nLEGEND", width: "11.2%", tone: "wine" },
      { title: "ROBBI\nJADE LEW", suit: "♣", subtitle: "THE\nWARRIOR", width: "12%", tone: "ink" },
    ],
  },
];
</script>
