<template>
  <section class="bets-page">
    <div class="roulette-felt" aria-hidden="true">
      <div class="roulette-board">
        <div class="roulette-top">
          <div class="zero-cell"><span>0</span></div>
          <div class="numbers-grid">
            <span class="n red"><span>3</span></span><span class="n black"><span>6</span></span><span class="n red"><span>9</span></span>
            <span class="n black"><span>12</span></span><span class="n red"><span>15</span></span><span class="n black"><span>18</span></span>
            <span class="n red"><span>21</span></span><span class="n black"><span>24</span></span><span class="n red"><span>27</span></span>
            <span class="n black"><span>30</span></span><span class="n red"><span>33</span></span><span class="n black"><span>36</span></span>

            <span class="n black"><span>2</span></span><span class="n red"><span>5</span></span><span class="n black"><span>8</span></span>
            <span class="n red"><span>11</span></span><span class="n black"><span>14</span></span><span class="n red"><span>17</span></span>
            <span class="n black"><span>20</span></span><span class="n red"><span>23</span></span><span class="n black"><span>26</span></span>
            <span class="n red"><span>29</span></span><span class="n black"><span>32</span></span><span class="n red"><span>35</span></span>

            <span class="n red"><span>1</span></span><span class="n black"><span>4</span></span><span class="n red"><span>7</span></span>
            <span class="n black"><span>10</span></span><span class="n red"><span>13</span></span><span class="n black"><span>16</span></span>
            <span class="n red"><span>19</span></span><span class="n black"><span>22</span></span><span class="n red"><span>25</span></span>
            <span class="n black"><span>28</span></span><span class="n red"><span>31</span></span><span class="n black"><span>34</span></span>
          </div>
          <div class="to1-col">
            <span><span>2 to 1</span></span>
            <span><span>2 to 1</span></span>
            <span><span>2 to 1</span></span>
          </div>
        </div>
        <div class="dozens-row">
          <span class="row-spacer" aria-hidden="true"></span>
          <span>1st 12</span>
          <span>2nd 12</span>
          <span>3rd 12</span>
          <span class="row-tail" aria-hidden="true"></span>
        </div>
        <div class="outside-row">
          <span class="row-spacer" aria-hidden="true"></span>
          <span>1 to 18</span>
          <span>EVEN</span>
          <span class="diamond red"></span>
          <span class="diamond black"></span>
          <span>ODD</span>
          <span>19 to 36</span>
          <span class="row-tail" aria-hidden="true"></span>
        </div>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts"></script>
