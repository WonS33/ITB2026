<script setup>
import AppNav from '@/components/AppNav.vue'
import { auth } from '@/auth'
</script>

<template>
  <AppNav v-if="auth.user" />
  <main class="container">
    <RouterView />
  </main>
</template>
