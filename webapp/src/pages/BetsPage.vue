<template>
  <section class="bets-page">
    <div class="roulette-felt" aria-hidden="true">
      <div class="roulette-board">
        <div class="roulette-top">
          <div class="zero-cell">0</div>
          <div class="numbers-grid">
            <span class="n red">3</span><span class="n black">6</span><span class="n red">9</span>
            <span class="n black">12</span><span class="n red">15</span><span class="n black">18</span>
            <span class="n red">21</span><span class="n black">24</span><span class="n red">27</span>
            <span class="n black">30</span><span class="n red">33</span><span class="n black">36</span>

            <span class="n black">2</span><span class="n red">5</span><span class="n black">8</span>
            <span class="n red">11</span><span class="n black">14</span><span class="n red">17</span>
            <span class="n black">20</span><span class="n red">23</span><span class="n black">26</span>
            <span class="n red">29</span><span class="n black">32</span><span class="n red">35</span>

            <span class="n red">1</span><span class="n black">4</span><span class="n red">7</span>
            <span class="n black">10</span><span class="n red">13</span><span class="n black">16</span>
            <span class="n red">19</span><span class="n black">22</span><span class="n red">25</span>
            <span class="n black">28</span><span class="n red">31</span><span class="n black">34</span>
          </div>
          <div class="to1-col">
            <span>2 to 1</span>
            <span>2 to 1</span>
            <span>2 to 1</span>
          </div>
        </div>
        <div class="dozens-row">
          <span>1st 12</span>
          <span>2nd 12</span>
          <span>3rd 12</span>
        </div>
        <div class="outside-row">
          <span>1 to 18</span>
          <span>EVEN</span>
          <span class="diamond red"></span>
          <span class="diamond black"></span>
          <span>ODD</span>
          <span>19 to 36</span>
        </div>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts"></script>
