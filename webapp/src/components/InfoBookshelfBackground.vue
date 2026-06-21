<template>
  <div class="info-library" aria-hidden="true">
    <div class="library-frame">
      <div
        v-for="(shelf, shelfIndex) in shelves"
        :key="`shelf-${shelfIndex}`"
        class="library-shelf"
      >
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
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "🍾", subtitle: "Я БУХАЛ\nИ БУДУ\nБУХАТЬ", width: "17.8%", tone: "wine" },
      { title: "PHIL\nIVEY", suit: "♣", subtitle: "READ\nPEOPLE", width: "12.6%", tone: "emerald" },
      { title: "CHRIS\nMONEYMAKER", suit: "♣", subtitle: "PLAY\nPOKER", width: "18.2%", tone: "emerald" },
      { title: "СЕРГЕЙ\nМАЯКИН", suit: "♥", subtitle: "КУЛИНАРНЫЕ\nРЕЦЕПТЫ", width: "18.4%", tone: "wine" },
      { title: "DANIEL\nNEGREANU", suit: "♦", subtitle: "POWER\nHOLD'EM", width: "17.4%", tone: "wine" },
      { title: "STU\nUNGAR", suit: "♣", subtitle: "ONE OF A\nKIND", width: "13.2%", tone: "ink" },
    ],
  },
  {
    books: [
      { title: "LINUS\nLOELIGER", suit: "♠", subtitle: "ELEMENTS\nOF POKER", width: "13.4%", tone: "emerald" },
      { title: "СЕРГЕЙ\nКУЗЬМИН", suit: "🤡", subtitle: "КАК СТАВИТЬ\nС ХУЙНЕЙ И\nВЫИГРЫВАТЬ!", width: "21.5%", tone: "wine" },
      { title: "VIKTOR\n\"ISILDUR1\"\nBLOM", suit: "♠", subtitle: "ONLINE\nLEGEND", width: "17.5%", tone: "emerald" },
      { title: "АЛЕКСАНДР\nИЛЛАРИОНОВ", suit: "🍆", subtitle: "ДРОЧИЛА", width: "20.4%", tone: "wine" },
      { title: "BERTRAND\nGROSPELLIER", suit: "♦", subtitle: "LIVE POKER\nSTRATEGY", width: "18.8%", tone: "emerald" },
    ],
    trophy: true,
  },
  {
    books: [
      { title: "TONY G", suit: "♦", subtitle: "POKER\nBRAT", width: "10.2%", tone: "wine" },
      { title: "JUSTIN\nBONOMO", suit: "♠", subtitle: "THE POKER\nTHINKER", width: "16.8%", tone: "ink" },
      { title: "PATRICK\nANTONIUS", suit: "♥", subtitle: "RELENTLESS", width: "17.6%", tone: "wine" },
      { title: "NIK\nAIRBALL", suit: "♣", subtitle: "EXPLOIT\nTHE LIVE GAME", width: "17.8%", tone: "emerald" },
      { title: "LIV\nBOEREE", suit: "♦", subtitle: "LADY\nLEGEND", width: "15%", tone: "wine" },
      { title: "ROBBI\nJADE LEW", suit: "♣", subtitle: "THE\nWARRIOR", width: "17%", tone: "ink" },
    ],
  },
];
</script>
